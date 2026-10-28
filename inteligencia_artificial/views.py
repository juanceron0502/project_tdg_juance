from django.http import JsonResponse
from django.shortcuts import render

from .services.prediccion_precios import obtener_estado_modelo
from .services.recomendaciones import cargar_recomendaciones


def panel_precios(request):
    estado = obtener_estado_modelo()

    contexto = {
        "modelo_disponible": estado["disponible"],
        "estado_modelo": estado["mensaje"],
        "modulo": "Predicción de precios agrícolas",
        "recomendaciones": cargar_recomendaciones(),   # nuevo
    }

    return render(request, "inteligencia_artificial/precios.html", contexto)


def precios_referencia(request):
    return render(
        request,
        "inteligencia_artificial/precios_referencia.html",
        {"recomendaciones": cargar_recomendaciones()},
    )


def api_recomendaciones(request):
    return JsonResponse(
        {"recomendaciones": cargar_recomendaciones()},
        json_dumps_params={"ensure_ascii": False},
    )