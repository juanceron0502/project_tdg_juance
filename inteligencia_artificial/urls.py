
from django.urls import path
from . import views

app_name = "inteligencia_artificial"

urlpatterns = [
    path("precios/",views.panel_precios,name="panel_precios",),
    path("precios-referencia/", views.precios_referencia, name="precios_referencia"),
    path("api/recomendaciones/", views.api_recomendaciones, name="api_recomendaciones"),
    
]
