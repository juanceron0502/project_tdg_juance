
from django.urls import path
from . import views

app_name = "inteligencia_artificial"

urlpatterns = [
    path(
        "precios/",
        views.panel_precios,
        name="panel_precios",
    ),
]
