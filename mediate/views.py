from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .forms import InitialForm, CheckForm, AnswerForm
from .models import Negotiation

import uuid

def index(request):
    return HttpResponse("Hello, world. You're at the polls index.")


def start(request):
    """
    as GET: prepare the form to input the initial data, returns to ids
        own_id: to lookup the result or check if the other side has already entered data
        share_id: the id to be shared with the other side
    """
    if request.method == "GET":
        form = InitialForm()
        return render(request, "mediate/start.html", {"form": form})

    elif request.method == "POST":
        form = InitialForm(request.POST)
        if form.is_valid():
            type = form.cleaned_data["type"]
            provided_value = form.cleaned_data["provided_value"]
            duration_input = form.cleaned_data["duration_input"]
            duration_display = form.cleaned_data["duration_display"]

            if type == "Bid":
                m = Negotiation(
                    bid_value=provided_value,
                    duration_display=duration_display,
                    duration_input=duration_input,
                )
            else:
                m = Negotiation(
                    ask_value=provided_value,
                    duration_display=duration_display,
                    duration_input=duration_input,
                )

            m.save()

            return_data = dict()
            if type == "Bid":
                return_data["share_id"] = m.ask_id
                return_data["own_id"] = m.bid_id
            else:
                return_data["share_id"] = m.bid_id
                return_data["own_id"] = m.ask_id

            messages.info(request, "created :-)")

        return render(
            request, "mediate/confirmation.html", {"return_data": return_data}
        )


def check(request, id=None):
    """
    this entry point provides access to the mediation core process
        1. when an "id" is provided in the url -> forward to the validation function
        2. no id in url, but "GET", provide a page to enter the id "check.html"
        3. "POST" -> forward to the validation function
    """

    # check if an id is provided in the url
    if id is not None:
        _id = id
    else:
        # check if an id is provided (by shortcut url from confirmation)
        _id = request.GET.get("id")

    print(f"requesting check for {_id}")

    n = None
    if _id is not None:
        id = uuid.UUID(_id)
        try:
            n = Negotiation.objects.filter(Q(bid_id=id) | Q(ask_id=id)).first()
        except ObjectDoesNotExist as odne:
            messages.warn(request, f"Not Found: {odne}")
            print("not found")
            form = CheckForm()
            return render(request, "mediate/check.html", {"form": form})

    if n is None:
        # check the anwser from the check.html page
        if request.method == "POST":
            form = CheckForm(request.POST)
            if form.is_valid():
                id = form.cleaned_data["id"]
                try:
                    n = Negotiation.objects.filter(Q(bid_id=id) | Q(ask_id=id)).first()
                    print(f"found: {n}")
                except ObjectDoesNotExist as odne:
                    print(odne)
                    messages.warn(request, f"Not Found: {odne}")
                    # provide a page, so the user can enter his/her id
                    form = CheckForm()
                    return render(request, "mediate/check.html", {"form": form})

        else:
            # provide a page, so the user can enter his/her id
            form = CheckForm()
            return render(request, "mediate/check.html", {"form": form})

    # reaching this point means we have a valid negotiation object

    # check the id for further steps
    # 1. check if the negotiation is complete
    if n.bid_value is not None and n.ask_value is not None:
        print("data complete")
        result = {"text": "data complete"}
        ## TODO: check and provide result
        if n.bid_value > n.ask_value:
            result = {"text": "negotiation is possible"}
        else:
            result = {"text": "negotiation is not possible"}
            
        return render(request, "mediate/result.html", {"result": result})
    # 2. if not complete, find out what is missing
    else:
        print(id)
        if id == n.bid_id and n.bid_value is None:
            print("bid_id provided and value missing")
            form = AnswerForm(id=id, type=('Bid', 'Bid'))
            return render(request, "mediate/answer.html", {"form": form})
        elif id == n.ask_id and n.ask_value is None:
            print("ask_id provided and value missing")
            form = AnswerForm({"id":id, "type":"Ask", "provided_value": 0})
            return render(request, "mediate/answer.html", {"form": form})
        elif id == n.ask_id and n.bid_value is None:
            print("ask id provided and bid value still missing")
            result = {"text": "bid value still missing"}
            return render(request, "mediate/result.html", {"result": result})
        elif id == n.bid_id and n.ask_value is None:
            print("bid id provided and ask value still missing")
            result = {"text": "ask value still missing"}
            return render(request, "mediate/result.html", {"result": result})

    print("strange")
    form = CheckForm()
    messages.warning(request, "strange")
    return render(request, "mediate/check.html", {"form": form})


def process(request):
    """
    process the answer from the other side
    """

    if request.method == "POST":
        form = AnswerForm(request.POST)
        if form.is_valid():
            id = form.cleaned_data["id"]
            type = form.cleaned_data["type"]
            provided_value = form.cleaned_data["provided_value"]
            if type == "Ask":
                n = Negotiation.objects.get(ask_id=id)
                n.ask_value = provided_value
                n.save()
                print("updated ask value")
                return HttpResponseRedirect(reverse("check", kwargs={"id": str(id)}))
            elif type == "Bid":
                n = Negotiation.objects.get(bid_id=id)
                n.bid_value = provided_value
                n.save()
                print("update bid value")
                return HttpResponseRedirect(reverse("check", kwargs={"id": id}))
                
