import uuid
from django.db import models

class Negotiation(models.Model):
    # the id for that case
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # the public id for the bid data
    bid_id = models.UUIDField(primary_key=False, default=uuid.uuid4, editable=False)
    bid_value = models.DecimalField(null=True, max_digits=16, decimal_places=2)

    # the public id for the ask data
    ask_id = models.UUIDField(primary_key=False, default=uuid.uuid4, editable=False)
    ask_value = models.DecimalField(null=True, max_digits=16, decimal_places=2)

    # the date the first entry was entered, so the countdown for the 2nd can be calculated
    start_date = models.DateTimeField(auto_now_add=True)
    
    # how long is 2nd entry
    duration_input = models.IntegerField(null=False, blank=False)
    duration_display =  models.IntegerField(null=False, blank=False)
