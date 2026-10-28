import json
from datetime import date
from pathlib import Path

from django.conf import settings

RUTA = Path(settings.BASE_DIR) / "inteligencia_artificial" / "modelos" / "recomendaciones.json"
_cache = {"mtime": None, "datos": []}

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _texto_mes(periodo):
    anio, mes = map(int, periodo.split("-"))
    return f"{MESES_ES[mes - 1]} de {anio}"


def _atraso_meses(mes_estimado):
    """'2025-01' -> meses transcurridos desde el mes estimado hasta hoy."""
    anio, mes = map(int, mes_estimado.split("-"))
    hoy = date.today()
    return (hoy.year - anio) * 12 + (hoy.month - mes)


def cargar_recomendaciones():
    try:
        mtime = RUTA.stat().st_mtime
    except FileNotFoundError:
        return []
    if _cache["mtime"] != mtime:            # se recarga solo si el archivo cambió
        with open(RUTA, encoding="utf-8") as f:
            datos = json.load(f)
        for r in datos:
            r["atraso_meses"] = _atraso_meses(r["mes_estimado"])
            _cache.update(mtime=mtime, datos=datos)
            r["mes_estimado_texto"] = _texto_mes(r["mes_estimado"])
            r["mes_base_texto"] = _texto_mes(r["mes_base"])
    return _cache["datos"]


def recomendacion_de(nombre_sipsa):
    if not nombre_sipsa:
        return None
    for r in cargar_recomendaciones():
        if r["producto"].lower() == nombre_sipsa.lower():
            return r
    return None