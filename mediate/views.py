import base64
import uuid
import qrcode

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from .forms import InitialForm, CheckForm, AnswerForm
from .models import Negotiation

from io import BytesIO

from logging import getLogger

logger = getLogger(__name__)

from PIL import Image

def index(request):
    return render(request, "mediate/index.html")


def start(request):
    """
    as GET: prepare the form to input the initial data, returns to ids
        own_id: to lookup the result or check if the other side has already entered data
        share_id: the id to be shared with the other side
    """
    if request.method == "GET":
        form = InitialForm(initial={"duration_input":5, "duration_display": 5})
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

            share_url = request.build_absolute_uri('/mediate/check/' + str(return_data["share_id"]))
            
            
            # use this logo when generating the qrcode
            logo = Image.open("sw.jpg")
            
            # taking base width
            basewidth = 100
            
            # adjust image size
            wpercent = (basewidth/float(logo.size[0]))
            hsize = int((float(logo.size[1])*float(wpercent)))
            logo = logo.resize((basewidth, hsize), Image.LANCZOS)
            QRcode = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_H
            )

            # adding URL or text to QRcode
            QRcode.add_data(share_url)
            
            # generating QR code
            QRcode.make()
            
            # color for the qr code
            fill_color = (3,103,166)

            # qr code background color
            back_color = "white"

            # adding color to QR code
            qr_image_pil = QRcode.make_image(
                fill_color=fill_color, back_color=back_color).convert("RGB")
            
            # set size of QR code
            pos = ((qr_image_pil.size[0] - logo.size[0]) // 2,
                (qr_image_pil.size[1] - logo.size[1]) // 2)
            qr_image_pil.paste(logo, pos)

            stream = BytesIO()
            qr_image_pil.save(stream, format="PNG")
            return_data["image"] = base64.b64encode(stream.getvalue()).decode("utf-8").replace('\n', '')     
            
            
            """
            qr_image = qrcode.make(share_url, box_size=15)
            qr_image_pil = qr_image.get_image()
            stream = BytesIO()
            qr_image_pil.save(stream, format="PNG")
            return_data["image"] = base64.b64encode(stream.getvalue()).decode("utf-8").replace('\n', '')     
            """
        return render(
            request, "mediate/confirmation.html", {"return_data": return_data}
        )


def check(request, id=None):
    """
    This is the entry for checking the different IDs. Threre are basically three use cases:
        1. The initiator checks his/her own id
            a. either the partner has not provided his/her input -> "data missing"
        2. The partner checks his/her (shared) id
            a. if not data has been provided -> forward to input page
        b. the partner has provided input -> negotiation is possible or not

    As entry, we have either 
        1. a page to provide a value
        2. a link, hence part of the url
        3. a POST request with the id as paramater
    """

    # for now the negotiation in null
    n = None

    # in a first step, check if the id has been provided
    # 1. as link in a GET request
    if request.method == "GET" and id is not None:
        try:
            id = uuid.UUID(id)
            n = Negotiation.objects.filter(Q(bid_id=id) | Q(ask_id=id)).first()
        except (ValueError, ObjectDoesNotExist) as e:
            messages.warning(request, f"{id} not found")
            logger.debug(f"{id} was provided as part of the url")

    # 2. as parameter in a POST request
    elif request.method == "POST":
        form = CheckForm(request.POST)
        if form.is_valid():
            id = form.cleaned_data["id"]
            try:
                n = Negotiation.objects.filter(Q(bid_id=id) | Q(ask_id=id)).first()
            except ObjectDoesNotExist as odne:
                messages.warning(request, f"{id} not found")
                logger.debug(f"{id} was provided as part of a POST request")
        else:
            messages.warning(request, "invalid data")

    # if either one of the above has found the negotiation, process it
    if n is not None:

        # 1. check if the negotiation is complete
        if n.bid_value is not None and n.ask_value is not None:
            logger.debug("negotiation data complete")
            result = {"text": "data complete"}
            
            if n.bid_value > n.ask_value:
                result = {"text": "negotiation is possible"}
            else:
                result = {"text": "negotiation is not possible"}
            
            logger.debug(result)
            return render(request, "mediate/result.html", {"result": result})
        # 2. if not complete, find out what is missing
        else:
            logger.debug("negotiation data is not yet complete")
            if id == n.bid_id and n.bid_value is None:
                logger.debug("bid_id provided and value missing")
                form = AnswerForm({"id":id, "type":"Bid", "provided_value": 0})
                return render(request, "mediate/answer.html", {"form": form})
            elif id == n.ask_id and n.ask_value is None:
                logger.debug("ask_id provided and value missing")
                form = AnswerForm({"id":id, "type":"Ask", "provided_value": 0})
                return render(request, "mediate/answer.html", {"form": form})
            elif id == n.ask_id and n.bid_value is None:
                logger.debug("ask id provided and bid value still missing")
                result = {"text": "bid value still missing"}
                return render(request, "mediate/result.html", {"result": result})
            elif id == n.bid_id and n.ask_value is None:
                logger.debug("bid id provided and ask value still missing")
                result = {"text": "ask value still missing"}
                return render(request, "mediate/result.html", {"result": result})

    
    form = CheckForm()
    logger.debug("no negotiation found")
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
                logger.debug("updated ask value")
                return HttpResponseRedirect(reverse("check", kwargs={"id": str(id)}))
            elif type == "Bid":
                n = Negotiation.objects.get(bid_id=id)
                n.bid_value = provided_value
                n.save()
                logger.debug("update bid value")
                return HttpResponseRedirect(reverse("check", kwargs={"id": id}))
                
    form = CheckForm()
    logger.debug("no negotiation found")
    return render(request, "mediate/check.html", {"form": form})
