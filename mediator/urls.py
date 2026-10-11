from django.urls import include, path

urlpatterns = [
    path("mediate/", include("mediate.urls"))
]
