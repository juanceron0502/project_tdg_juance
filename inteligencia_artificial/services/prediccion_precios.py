"""Estado y consulta del módulo de precios de referencia.

Lee lo que genera entrenar_modelos.py (recomendaciones.json) a través del
servicio recomendaciones.py. Ya no depende de artifacts/modelo_precios.joblib.
"""
from .recomendaciones import cargar_recomendaciones, recomendacion_de


def obtener_estado_modelo():
    recomendaciones = cargar_recomendaciones()

    if not recomendaciones:
        return {
            "disponible": False,
            "desactualizado": False,
            "productos": [],
            "mensaje": (
                "Todavía no hay recomendaciones generadas. "
                "Ejecute entrenar_modelos.py para crearlas."
            ),
        }

    atraso = max(r["atraso_meses"] for r in recomendaciones)
    productos = [r["producto"] for r in recomendaciones]
    mensaje = (
        f"Referencias disponibles para {len(productos)} productos, "
        f"con datos del SIPSA hasta {recomendaciones[0]['mes_base']}."
    )
    if atraso > 1:
        mensaje += (
            f" La estimación más reciente es para {recomendaciones[0]['mes_estimado']} "
            f"y ya pasaron {atraso} meses: conviene actualizar los datos y volver a entrenar."
        )

    return {
        "disponible": True,
        "desactualizado": atraso > 1,
        "productos": productos,
        "mensaje": mensaje,
    }


def precio_referencia(producto_sipsa):
    """Referencia de precio para un producto, usando el nombre del SIPSA."""
    r = recomendacion_de(producto_sipsa)
    if r is None:
        return {"ok": False, "mensaje": "No hay referencia de precio para este producto."}
    return {
        "ok": True,
        "precio_estimado": r["precio_estimado"],
        "rango_bajo": r["rango_bajo"],
        "rango_alto": r["rango_alto"],
        "confianza": r["confianza"],
        "mes_estimado": r["mes_estimado"],
        "mensaje": " ".join(r["mensaje"][:2]),
    }