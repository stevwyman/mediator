import uuid
from datetime import timedelta

from django.db import connection, models, transaction
from django.utils import timezone


class Negotiation(models.Model):
    # Private key. Callers only ever see bid_id or ask_id.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    bid_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    bid_value = models.DecimalField(null=True, max_digits=16, decimal_places=2)

    ask_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    ask_value = models.DecimalField(null=True, max_digits=16, decimal_places=2)

    # Set once both reserves are in. The amounts are cleared in the same step.
    result = models.BooleanField(null=True)
    completed_at = models.DateTimeField(null=True)

    # When the first reserve was stored. The second party must respond by
    # start_date + duration_input days.
    start_date = models.DateTimeField(auto_now_add=True)
    duration_input = models.IntegerField()
    # How many days the yes/no result stays available after completed_at.
    duration_display = models.IntegerField()

    def input_deadline(self):
        return self.start_date + timedelta(days=self.duration_input)

    def display_deadline(self):
        if self.completed_at is None:
            return None
        return self.completed_at + timedelta(days=self.duration_display)

    def party_ids(self, side):
        """Return (owner token, token to share with the other party)."""
        if side == "Bid":
            return self.bid_id, self.ask_id
        if side == "Ask":
            return self.ask_id, self.bid_id
        raise ValueError("side must be Bid or Ask")

    @classmethod
    def begin(cls, side, value, duration_input, duration_display):
        """Build an unsaved negotiation with one reserve filled in."""
        negotiation = cls(
            bid_id=uuid.uuid4(),
            ask_id=uuid.uuid4(),
            duration_input=duration_input,
            duration_display=duration_display,
        )
        if side == "Bid":
            negotiation.bid_value = value
        elif side == "Ask":
            negotiation.ask_value = value
        else:
            raise ValueError("side must be Bid or Ask")
        return negotiation

    def expire_if_needed(self):
        """
        Delete this row when its window has closed.

        Returns "input", "display", or None when the row is still active.
        """
        now = timezone.now()
        if self.result is None:
            if now >= self.input_deadline():
                self.delete()
                return "input"
            return None
        deadline = self.display_deadline()
        if deadline is None or now >= deadline:
            self.delete()
            return "display"
        return None

    def finalize_if_complete(self):
        """Store the yes/no result and delete both reserve prices."""
        if self.result is not None:
            return
        if self.bid_value is None or self.ask_value is None:
            return
        possible = self.bid_value >= self.ask_value
        type(self).objects.filter(
            pk=self.pk,
            result__isnull=True,
            bid_value__isnull=False,
            ask_value__isnull=False,
        ).update(
            result=possible,
            bid_value=None,
            ask_value=None,
            completed_at=timezone.now(),
        )
        self.refresh_from_db()

    def submit_value(self, side, value):
        """
        Record one side's reserve exactly once.

        Returns "saved", "duplicate", "expired", or "missing".
        """
        field = "bid_value" if side == "Bid" else "ask_value"
        with transaction.atomic():
            current = _locked_negotiation(self.pk)
            if current is None:
                return "missing"
            if current.result is not None or getattr(current, field) is not None:
                return "duplicate"
            if timezone.now() >= current.input_deadline():
                current.delete()
                return "expired"
            updated = type(self).objects.filter(
                pk=current.pk,
                result__isnull=True,
                **{f"{field}__isnull": True},
            ).update(**{field: value})
            if updated != 1:
                return "duplicate"
            current.refresh_from_db()
            current.finalize_if_complete()
            return "saved"

    @classmethod
    def purge_expired(cls):
        """Delete every negotiation whose input or result window has closed."""
        now = timezone.now()
        expired = []
        rows = cls.objects.only(
            "id",
            "start_date",
            "duration_input",
            "duration_display",
            "result",
            "completed_at",
        ).iterator()
        for row in rows:
            if row.result is None:
                if now >= row.input_deadline():
                    expired.append(row.pk)
            else:
                deadline = row.display_deadline()
                if deadline is None or now >= deadline:
                    expired.append(row.pk)
        if expired:
            cls.objects.filter(pk__in=expired).delete()


def _locked_negotiation(pk):
    queryset = Negotiation.objects.filter(pk=pk)
    if connection.features.has_select_for_update:
        queryset = queryset.select_for_update()
    return queryset.first()
