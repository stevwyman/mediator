import logging
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase, Client, override_settings
from django.utils import timezone

from mediate.logging import RedactingFormatter
from mediate.middleware import TrustedProxyMiddleware
from mediate.models import Negotiation

class Working_Mediation(TestCase):
    own_id = None
    share_id = None

    def check_own_id_data_missing(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertEqual(response.context["result"]["text"], "ask value still missing")

    def check_own_id_data_complete(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["result"])
        self.assertEqual(response.context["result"]["text"], "negotiation is possible")

    def update_other_side(self) -> None:
        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.share_id),
        )
        self.assertEqual(response.status_code, 200)

        response = client.post(
            "/mediate/process",
            data={"id": self.share_id, "type": "Ask", "provided_value": 100},
            follow=True
        )

        self.assertRedirects(
            response,
            "/mediate/check/" + str(self.share_id),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )

        self.assertIsNotNone(response.context["result"])

        # as Ask is 100 and bis is 110, negotiation is possible
        self.assertEqual(response.context["result"]["text"], "negotiation is possible")

    def check_other_side(self) -> None:

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)

    def setUp(self) -> None:
        """
        bid 110: I would buy for up to 110, hence I would pay max 100
        """
        client = Client(enforce_csrf_checks=False)
        response = client.post(
            "/mediate/start",
            data={
                "type": "Bid",
                "provided_value": 110,
                "duration_input": 2,
                "duration_display": 2,
            },
        )
        self.assertEqual(response.status_code, 200)

        self.own_id = response.context["return_data"]["own_id"]
        self.share_id = response.context["return_data"]["share_id"]

        self.assertIsNotNone(self.own_id)
        self.assertIsNotNone(self.share_id)

    def test_mediation(self) -> None:
        self.check_own_id_data_missing()
        self.update_other_side()
        self.check_own_id_data_complete()
        self.check_other_side()
        self.check_other_side()
        self.check_own_id_data_complete()


class Not_Working_Mediation(TestCase):
    own_id = None
    share_id = None

    def setUp(self) -> None:
        """
        bid 100: I would buy for up to 100, hence I would pay max 100
        """
        client = Client(enforce_csrf_checks=False)
        response = client.post(
            "/mediate/start",
            data={
                "type": "Bid",
                "provided_value": 100,
                "duration_input": 2,
                "duration_display": 2,
            },
        )
        self.assertEqual(response.status_code, 200)

        self.own_id = response.context["return_data"]["own_id"]
        self.share_id = response.context["return_data"]["share_id"]

        self.assertIsNotNone(self.own_id)
        self.assertIsNotNone(self.share_id)

    def test_own_id(self) -> None:

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.own_id),
        )
        self.assertEqual(response.status_code, 200)

    def test_shared(self) -> None:
        """
        Ask 110: Seller would sell for min 110
        """

        client = Client(enforce_csrf_checks=False)
        response = client.get(
            "/mediate/check/" + str(self.share_id),
        )
        self.assertEqual(response.status_code, 200)

        response = client.post(
            "/mediate/process",
            data={"id": self.share_id, "type": "Ask", "provided_value": 110},
            follow=True
        )

        self.assertRedirects(
            response,
            "/mediate/check/" + str(self.share_id),
            status_code=302,
            target_status_code=200,
            fetch_redirect_response=True,
        )

        self.assertIsNotNone(response.context["result"])

        # as Ask is 110 and bis is 100, no negotiation is possible
        self.assertEqual(response.context["result"]["text"], "negotiation is not possible")


def _start(client, side, value, duration_input=2, duration_display=2):
    response = client.post(
        "/mediate/start",
        data={
            "type": side,
            "provided_value": str(value),
            "duration_input": duration_input,
            "duration_display": duration_display,
        },
    )
    return response


class WriteOnceAndWipe(TestCase):
    def test_resubmitting_does_not_change_the_result_or_keep_prices(self):
        client = Client(enforce_csrf_checks=False)
        started = _start(client, "Bid", "100.00")
        own_id = started.context["return_data"]["own_id"]
        share_id = started.context["return_data"]["share_id"]

        response = client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Ask", "provided_value": "150.00"},
            follow=True,
        )
        self.assertEqual(response.context["result"]["text"], "negotiation is not possible")

        client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Ask", "provided_value": "1.00"},
            follow=True,
        )
        client.post(
            "/mediate/process",
            data={"id": own_id, "type": "Bid", "provided_value": "1000.00"},
            follow=True,
        )
        checked = client.get("/mediate/check/" + str(own_id))
        self.assertEqual(checked.context["result"]["text"], "negotiation is not possible")

        stored = Negotiation.objects.get()
        self.assertIsNone(stored.bid_value)
        self.assertIsNone(stored.ask_value)
        self.assertFalse(stored.result)
        self.assertIsNotNone(stored.completed_at)

    def test_tampered_side_does_not_overwrite_the_other_price(self):
        client = Client(enforce_csrf_checks=False)
        started = _start(client, "Bid", "100.00")
        share_id = started.context["return_data"]["share_id"]

        client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Bid", "provided_value": "1.00"},
        )

        stored = Negotiation.objects.get()
        self.assertEqual(stored.bid_value, Decimal("100.00"))
        self.assertIsNone(stored.ask_value)
        self.assertIsNone(stored.result)

    def test_decimal_boundary_matches_exactly(self):
        client = Client(enforce_csrf_checks=False)
        started = _start(client, "Bid", "10.10")
        share_id = started.context["return_data"]["share_id"]
        response = client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Ask", "provided_value": "10.10"},
            follow=True,
        )
        self.assertEqual(response.context["result"]["text"], "negotiation is possible")

        started = _start(client, "Bid", "10.10")
        share_id = started.context["return_data"]["share_id"]
        response = client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Ask", "provided_value": "10.11"},
            follow=True,
        )
        self.assertEqual(response.context["result"]["text"], "negotiation is not possible")


class Expiry(TestCase):
    def test_unanswered_offer_is_deleted_after_the_input_window(self):
        client = Client(enforce_csrf_checks=False)
        started = _start(client, "Bid", "80")
        own_id = started.context["return_data"]["own_id"]
        share_id = started.context["return_data"]["share_id"]
        stored = Negotiation.objects.get()
        stored.start_date = timezone.now() - timedelta(days=3)
        stored.save(update_fields=["start_date"])

        late = client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Ask", "provided_value": "70"},
        )
        self.assertContains(late, "This negotiation has expired.")
        self.assertFalse(Negotiation.objects.exists())

        missing = client.get("/mediate/check/" + str(own_id))
        self.assertContains(missing, "No negotiation matches that code.")

    def test_result_is_deleted_after_the_display_window(self):
        client = Client(enforce_csrf_checks=False)
        started = _start(client, "Ask", "40")
        own_id = started.context["return_data"]["own_id"]
        share_id = started.context["return_data"]["share_id"]
        client.post(
            "/mediate/process",
            data={"id": share_id, "type": "Bid", "provided_value": "40"},
            follow=True,
        )
        stored = Negotiation.objects.get()
        stored.completed_at = timezone.now() - timedelta(days=3)
        stored.save(update_fields=["completed_at"])

        response = client.get("/mediate/check/" + str(own_id))
        self.assertContains(response, "The result is no longer available.")
        self.assertFalse(Negotiation.objects.exists())

    def test_opening_the_site_deletes_other_expired_rows(self):
        expired = Negotiation.objects.create(
            bid_value=Decimal("50"),
            duration_input=2,
            duration_display=2,
        )
        expired.start_date = timezone.now() - timedelta(days=5)
        expired.save(update_fields=["start_date"])
        fresh = Negotiation.objects.create(
            bid_value=Decimal("10"),
            duration_input=2,
            duration_display=2,
        )

        Client().get("/mediate/")
        self.assertFalse(Negotiation.objects.filter(pk=expired.pk).exists())
        self.assertTrue(Negotiation.objects.filter(pk=fresh.pk).exists())

    def test_existing_finished_rows_drop_their_prices(self):
        import importlib

        from django.apps import apps

        migration = importlib.import_module(
            "mediate.migrations.0002_negotiation_result_and_unique_ids"
        )
        Negotiation.objects.create(
            bid_value=Decimal("10"),
            ask_value=Decimal("12"),
            duration_input=2,
            duration_display=2,
        )
        migration.finalize_completed(apps, None)
        stored = Negotiation.objects.get()
        self.assertFalse(stored.result)
        self.assertIsNone(stored.bid_value)
        self.assertIsNone(stored.ask_value)
        self.assertEqual(stored.completed_at, stored.start_date)


class StartFailures(TestCase):
    def test_invalid_form_does_not_save(self):
        client = Client(enforce_csrf_checks=False)
        response = client.post(
            "/mediate/start",
            data={
                "type": "Bid",
                "provided_value": "12.50",
                "duration_input": 1,
                "duration_display": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Begin mediation")
        self.assertFalse(Negotiation.objects.exists())

    def test_oversized_price_is_rejected(self):
        client = Client(enforce_csrf_checks=False)
        response = _start(client, "Bid", "100000000000000.00")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Begin mediation")
        self.assertFalse(Negotiation.objects.exists())

    def test_qr_failure_does_not_save(self):
        client = Client(enforce_csrf_checks=False)
        with patch("mediate.views.build_share_qr", side_effect=OSError("missing logo")):
            response = _start(client, "Ask", "20")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing was saved")
        self.assertFalse(Negotiation.objects.exists())


class LoggingAndProxy(TestCase):
    def test_log_formatter_redacts_negotiation_codes(self):
        token = "11111111-1111-4111-8111-111111111111"
        record = logging.LogRecord(
            name="django.server",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="GET /mediate/check/%s",
            args=(token,),
            exc_info=None,
        )
        rendered = RedactingFormatter("{message}", style="{").format(record)
        self.assertNotIn(token, rendered)
        self.assertIn("[redacted]", rendered)

    @override_settings(TRUSTED_PROXY_IPS=["10.0.0.8"])
    def test_forwarded_headers_from_other_clients_are_removed(self):
        request = RequestFactory().get(
            "/mediate/",
            HTTP_X_FORWARDED_HOST="evil.example",
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR="203.0.113.9",
        )
        seen = {}

        def capture(captured):
            seen["host"] = captured.META.get("HTTP_X_FORWARDED_HOST")
            seen["proto"] = captured.META.get("HTTP_X_FORWARDED_PROTO")
            return HttpResponse("ok")

        TrustedProxyMiddleware(capture)(request)
        self.assertIsNone(seen["host"])
        self.assertIsNone(seen["proto"])

    @override_settings(TRUSTED_PROXY_IPS=["10.0.0.8"])
    def test_forwarded_headers_from_the_proxy_are_kept(self):
        request = RequestFactory().get(
            "/mediate/",
            HTTP_X_FORWARDED_HOST="mediate.example",
            HTTP_X_FORWARDED_PROTO="https",
            REMOTE_ADDR="10.0.0.8",
        )
        seen = {}

        def capture(captured):
            seen["host"] = captured.META.get("HTTP_X_FORWARDED_HOST")
            seen["proto"] = captured.META.get("HTTP_X_FORWARDED_PROTO")
            return HttpResponse("ok")

        TrustedProxyMiddleware(capture)(request)
        self.assertEqual(seen["host"], "mediate.example")
        self.assertEqual(seen["proto"], "https")
