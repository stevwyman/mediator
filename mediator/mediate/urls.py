from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("start", views.start, name="start"),
    path("check", views.check, name="check"),
    path("check/<str:id>", views.check, name="check"),
    path("process", views.process, name="process")
]