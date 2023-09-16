from django import forms

class InitialForm(forms.Form):
    
    CHOICES = (('Bid', 'Bid'),('Ask', 'Ask'))
    type = forms.ChoiceField(choices=CHOICES)
    provided_value = forms.FloatField(required=True, min_value=0)
    duration_input = forms.IntegerField(required=True, max_value=14, min_value=2)
    duration_display = forms.IntegerField(required=True, max_value=14, min_value=2)

class AnswerForm(forms.Form):

    type = forms.CharField(widget=forms.HiddenInput(), required=True)
    provided_value = forms.FloatField(required=True, min_value=0)
    id = forms.UUIDField(widget=forms.HiddenInput(), required=True)

class CheckForm(forms.Form):

    id = forms.UUIDField()