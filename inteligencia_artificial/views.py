from django.shortcuts import render
from .services.prediccion_precios import obtener_estado_modelo
# Create your views here.





def panel_precios(request):
    estado = obtener_estado_modelo()

    contexto = {
        "modelo_disponible": estado["disponible"],
        "estado_modelo": estado["mensaje"],
        "modulo": "Predicción de precios agrícolas",
    }

    return render(
        request,
        "inteligencia_artificial/precios.html",
        contexto,
    )
