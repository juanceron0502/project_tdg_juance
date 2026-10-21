
from pathlib import Path

import joblib
import pandas as pd
from django.conf import settings


# Los archivos de IA estarán separados del código de la tienda.
DIRECTORIO_IA = (
    Path(settings.BASE_DIR)
    / "inteligencia_artificial"
    / "artifacts"
)

ARCHIVO_MODELO = DIRECTORIO_IA / "modelo_precios.joblib"


def obtener_estado_modelo():
    """
    Informa si hay un modelo entrenado disponible.
    No genera predicciones si todavía no existe.
    """
    if not ARCHIVO_MODELO.exists():
        return {
            "disponible": False,
            "mensaje": (
                "Todavía no existe un modelo entrenado. "
                "Primero debemos recopilar y validar datos agrícolas."
            ),
        }

    try:
        artefacto = joblib.load(ARCHIVO_MODELO)

        return {
            "disponible": True,
            "mensaje": "Modelo entrenado disponible.",
            "modelo": artefacto,
        }

    except (OSError, ValueError, EOFError):
        return {
            "disponible": False,
            "mensaje": (
                "No se pudo cargar el modelo. "
                "Es necesario revisar o volver a entrenar el archivo."
            ),
        }


def predecir_precio(datos):
    """
    Recibe las variables que espera el modelo entrenado.
    El artefacto debe contener el estimador y sus columnas.
    """
    estado = obtener_estado_modelo()

    if not estado["disponible"]:
        return {
            "ok": False,
            "mensaje": estado["mensaje"],
        }

    artefacto = estado["modelo"]
    modelo = artefacto["modelo"]
    columnas = artefacto["columnas"]

    try:
        entrada = pd.DataFrame([datos])
        entrada = entrada[columnas]

        precio = float(modelo.predict(entrada)[0])

        if not pd.notna(precio) or precio <= 0:
            return {
                "ok": False,
                "mensaje": "El modelo produjo un precio no válido.",
            }

        return {
            "ok": True,
            "precio_estimado": round(precio, 2),
            "mensaje": "Predicción generada por el modelo entrenado.",
        }

    except (KeyError, TypeError, ValueError) as error:
        return {
            "ok": False,
            "mensaje": f"No fue posible procesar las variables: {error}",
        }
