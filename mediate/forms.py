from decimal import Decimal

from django import forms


class InitialForm(forms.Form):
    CHOICES = (("Bid", "Bid"), ("Ask", "Ask"))
    type = forms.ChoiceField(choices=CHOICES)
    provided_value = forms.DecimalField(
        label="Reserve price",
        required=True,
        min_value=Decimal("0"),
        max_digits=16,
        decimal_places=2,
    )
    duration_input = forms.IntegerField(
        label="Days for the other party to respond",
        help_text="If they do not respond in time, the offer and your price are deleted.",
        required=True,
        min_value=2,
        max_value=14,
    )
    duration_display = forms.IntegerField(
        label="Days to show the result",
        help_text="After both sides have responded, the yes or no stays available for this many days.",
        required=True,
        min_value=2,
        max_value=14,
    )


class AnswerForm(forms.Form):
    CHOICES = (("Bid", "Bid"), ("Ask", "Ask"))
    type = forms.ChoiceField(choices=CHOICES, widget=forms.HiddenInput(), required=True)
    provided_value = forms.DecimalField(
        label="Reserve price",
        required=True,
        min_value=Decimal("0"),
        max_digits=16,
        decimal_places=2,
    )
    id = forms.UUIDField(widget=forms.HiddenInput(), required=True)


class CheckForm(forms.Form):
    id = forms.UUIDField()
