import base64
import uuid
from io import BytesIO
from logging import getLogger

import qrcode
from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from PIL import Image

from .forms import AnswerForm, CheckForm, InitialForm
from .models import Negotiation

logger = getLogger(__name__)

NOT_FOUND = "No negotiation matches that code."
INVALID_CODE = "That code is not valid."
EXPIRED_INPUT = "This negotiation has expired."
EXPIRED_RESULT = "The result is no longer available."
ALREADY_SUBMITTED = "This response was already submitted."


def index(request):
    Negotiation.purge_expired()
    return render(request, "mediate/index.html")


def start(request):
    """
    Collect the first reserve price and return the two access codes.

    own_id looks up this party's side. share_id is the code given to the
    other party. The row is saved only after the share QR code is built,
    so a failure here does not leave a negotiation nobody can open.
    """
    Negotiation.purge_expired()
    if request.method != "POST":
        form = InitialForm(initial={"duration_input": 5, "duration_display": 5})
        return render(request, "mediate/start.html", {"form": form})

    form = InitialForm(request.POST)
    if not form.is_valid():
        return render(request, "mediate/start.html", {"form": form})

    side = form.cleaned_data["type"]
    negotiation = Negotiation.begin(
        side=side,
        value=form.cleaned_data["provided_value"],
        duration_input=form.cleaned_data["duration_input"],
        duration_display=form.cleaned_data["duration_display"],
    )
    own_id, share_id = negotiation.party_ids(side)
    share_url = request.build_absolute_uri(f"/mediate/check/{share_id}")
    try:
        image = build_share_qr(share_url)
    except Exception:
        logger.exception("Could not build the share QR code")
        form.add_error(
            None,
            "Could not create the share code. Nothing was saved. Please try again.",
        )
        return render(request, "mediate/start.html", {"form": form})

    negotiation.save()
    return render(
        request,
        "mediate/confirmation.html",
        {
            "return_data": {
                "share_id": share_id,
                "own_id": own_id,
                "image": image,
            }
        },
    )


def check(request, id=None):
    """
    Look up a negotiation by one party's code.

    A code whose window has closed is deleted. A finished negotiation
    returns only whether a deal is possible.
    """
    token, early = _token_from_request(request, id)
    if early is not None:
        Negotiation.purge_expired()
        return early
    if token is None:
        Negotiation.purge_expired()
        return render(request, "mediate/check.html", {"form": CheckForm()})

    response = _render_for_token(request, token)
    Negotiation.purge_expired()
    return response


def process(request):
    """Record the second reserve, once, then return to the result page."""
    if request.method != "POST":
        Negotiation.purge_expired()
        return render(request, "mediate/check.html", {"form": CheckForm()})

    form = AnswerForm(request.POST)
    if not form.is_valid():
        return render(request, "mediate/answer.html", {"form": form})

    token = form.cleaned_data["id"]
    negotiation = Negotiation.objects.filter(Q(bid_id=token) | Q(ask_id=token)).first()
    if negotiation is None:
        messages.warning(request, NOT_FOUND)
        Negotiation.purge_expired()
        return render(request, "mediate/check.html", {"form": CheckForm()})

    side = "Bid" if token == negotiation.bid_id else "Ask"
    if form.cleaned_data["type"] != side:
        messages.warning(request, "invalid data")
        Negotiation.purge_expired()
        return render(request, "mediate/check.html", {"form": CheckForm()})

    status = negotiation.submit_value(side, form.cleaned_data["provided_value"])
    Negotiation.purge_expired()
    if status == "expired":
        return render(
            request, "mediate/result.html", {"result": {"text": EXPIRED_INPUT}}
        )
    if status == "missing":
        messages.warning(request, NOT_FOUND)
        return render(request, "mediate/check.html", {"form": CheckForm()})
    if status == "duplicate":
        messages.info(request, ALREADY_SUBMITTED)
    return HttpResponseRedirect(reverse("check", kwargs={"id": str(token)}))


def build_share_qr(share_url):
    """Return a base64 PNG of the share link. Raises if the logo cannot be read."""
    logo_path = settings.BASE_DIR / "sw.jpg"
    with Image.open(logo_path) as logo:
        basewidth = 100
        wpercent = basewidth / float(logo.size[0])
        hsize = int(float(logo.size[1]) * float(wpercent))
        resized = logo.resize((basewidth, hsize), Image.LANCZOS)
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
        code.add_data(share_url)
        code.make(fit=True)
        qr_image = code.make_image(
            fill_color=(3, 103, 166), back_color="white"
        ).convert("RGB")
        pos = (
            (qr_image.size[0] - resized.size[0]) // 2,
            (qr_image.size[1] - resized.size[1]) // 2,
        )
        qr_image.paste(resized, pos)
        stream = BytesIO()
        qr_image.save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode("ascii")


def _token_from_request(request, raw_id):
    if request.method == "GET" and raw_id is not None:
        try:
            return uuid.UUID(str(raw_id)), None
        except ValueError:
            messages.warning(request, INVALID_CODE)
            return None, render(request, "mediate/check.html", {"form": CheckForm()})

    if request.method == "POST":
        form = CheckForm(request.POST)
        if not form.is_valid():
            messages.warning(request, "invalid data")
            return None, render(request, "mediate/check.html", {"form": form})
        return form.cleaned_data["id"], None

    return None, None


def _render_for_token(request, token):
    negotiation = Negotiation.objects.filter(Q(bid_id=token) | Q(ask_id=token)).first()
    if negotiation is None:
        messages.warning(request, NOT_FOUND)
        return render(request, "mediate/check.html", {"form": CheckForm()})

    expired = negotiation.expire_if_needed()
    if expired == "input":
        return render(
            request, "mediate/result.html", {"result": {"text": EXPIRED_INPUT}}
        )
    if expired == "display":
        return render(
            request, "mediate/result.html", {"result": {"text": EXPIRED_RESULT}}
        )

    negotiation.finalize_if_complete()
    if negotiation.result is not None:
        text = (
            "negotiation is possible"
            if negotiation.result
            else "negotiation is not possible"
        )
        return render(request, "mediate/result.html", {"result": {"text": text}})

    if token == negotiation.bid_id and negotiation.bid_value is None:
        form = AnswerForm(initial={"id": token, "type": "Bid"})
        return render(request, "mediate/answer.html", {"form": form})
    if token == negotiation.ask_id and negotiation.ask_value is None:
        form = AnswerForm(initial={"id": token, "type": "Ask"})
        return render(request, "mediate/answer.html", {"form": form})
    if token == negotiation.ask_id and negotiation.bid_value is None:
        return render(
            request,
            "mediate/result.html",
            {"result": {"text": "bid value still missing"}},
        )
    if token == negotiation.bid_id and negotiation.ask_value is None:
        return render(
            request,
            "mediate/result.html",
            {"result": {"text": "ask value still missing"}},
        )

    messages.warning(request, NOT_FOUND)
    return render(request, "mediate/check.html", {"form": CheckForm()})
