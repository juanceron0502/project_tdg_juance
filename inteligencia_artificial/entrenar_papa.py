
from pathlib import Path
import re
import unicodedata

import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
ARCHIVO_CSV = BASE_DIR / "datos" / "papa_semanal.csv"
DIRECTORIO_MODELOS = BASE_DIR / "modelos"
ARCHIVO_MODELO = DIRECTORIO_MODELOS / "papa_semanal.joblib"
ARCHIVO_RESULTADOS = DIRECTORIO_MODELOS / "comparacion_modelos.csv"

COLUMNA_FECHA = "Fecha"
COLUMNA_PRODUCTO = "Producto"
COLUMNA_MERCADO = "Mercado"
COLUMNA_PRECIO = "Precio promedio por kilogramo*"

PRODUCTO_OBJETIVO = "papa parda pastusa"
MERCADO_OBJETIVO = "Bogotá, D.C., Corabastos"

# Las semanas terminan el domingo.
AGREGAR_POR_SEMANA = True

MINIMO_SEMANAS = 26
PORCENTAJE_ENTRENAMIENTO = 0.80

COLUMNAS_MODELO = [
    "precio_actual",
    "rezago_1",
    "rezago_2",
    "rezago_3",
    "media_4_semanas",
]


# ==========================================================
# NORMALIZACIÓN
# ==========================================================

def normalizar_texto(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    return re.sub(r"\s+", " ", texto)


def convertir_precio(columna):
    """
    Interpreta formatos habituales:
    2500, 2.500, 2500,50 y 2.500,50.

    Verifica el formato de tu CSV antes de usarlo con
    datos que tengan separadores diferentes.
    """

    def convertir(valor):
        if pd.isna(valor):
            return np.nan

        texto = str(valor).strip()
        texto = texto.replace("COP", "").replace("$", "")
        texto = texto.replace(" ", "")
        texto = re.sub(r"[^\d,.\-]", "", texto)

        if not texto or texto in {"-", ".", ","}:
            return np.nan

        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "")
                texto = texto.replace(",", ".")
            else:
                texto = texto.replace(",", "")

        elif "," in texto:
            partes = texto.split(",")

            if len(partes) == 2 and len(partes[1]) in (1, 2):
                texto = texto.replace(",", ".")
            else:
                texto = texto.replace(",", "")

        elif "." in texto:
            partes = texto.split(".")

            if len(partes) > 2:
                texto = texto.replace(".", "")
            elif len(partes) == 2 and len(partes[1]) == 3:
                texto = texto.replace(".", "")

        try:
            return float(texto)
        except ValueError:
            return np.nan

    return columna.apply(convertir)


# ==========================================================
# CARGA DE DATOS
# ==========================================================

def cargar_datos():
    if not ARCHIVO_CSV.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo: {ARCHIVO_CSV}"
        )

    df = pd.read_csv(
        ARCHIVO_CSV,
        sep=";",
        encoding="utf-8-sig",
        dtype=str
    )

    df.columns = df.columns.str.strip()

    requeridas = {
        COLUMNA_FECHA,
        COLUMNA_PRODUCTO,
        COLUMNA_MERCADO,
        COLUMNA_PRECIO,
    }

    faltantes = requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas: {sorted(faltantes)}. "
            f"Columnas detectadas: {df.columns.tolist()}"
        )

    df[COLUMNA_FECHA] = pd.to_datetime(
        df[COLUMNA_FECHA],
        errors="coerce",
        dayfirst=True
    )

    df[COLUMNA_PRECIO] = convertir_precio(
        df[COLUMNA_PRECIO]
    )

    df = df.dropna(
        subset=[COLUMNA_FECHA, COLUMNA_PRECIO]
    )

    df = df[df[COLUMNA_PRECIO] > 0].copy()

    df["_producto"] = df[COLUMNA_PRODUCTO].apply(
        normalizar_texto
    )
    df["_mercado"] = df[COLUMNA_MERCADO].apply(
        normalizar_texto
    )

    producto = normalizar_texto(PRODUCTO_OBJETIVO)
    mercado = normalizar_texto(MERCADO_OBJETIVO)

    if not (df["_producto"] == producto).any():
        print("Productos disponibles:")
        print(df[COLUMNA_PRODUCTO].drop_duplicates().head(50).to_list())
        raise ValueError(
            f"No se encontró el producto: {PRODUCTO_OBJETIVO}"
        )

    if not (df["_mercado"] == mercado).any():
        print("Mercados disponibles:")
        print(df[COLUMNA_MERCADO].drop_duplicates().head(50).to_list())
        raise ValueError(
            f"No se encontró el mercado: {MERCADO_OBJETIVO}"
        )

    df = df[
        (df["_producto"] == producto)
        & (df["_mercado"] == mercado)
    ].copy()

    if df.empty:
        raise ValueError(
            "No hay registros para el producto y mercado seleccionados."
        )

    df = df.sort_values(COLUMNA_FECHA)

    if AGREGAR_POR_SEMANA:
        df["Semana"] = (
            df[COLUMNA_FECHA]
            .dt.to_period("W-SUN")
            .dt.start_time
        )

        precios = df.groupby("Semana")[COLUMNA_PRECIO].mean()
    else:
        precios = df.groupby(COLUMNA_FECHA)[COLUMNA_PRECIO].mean()

    precios = precios.sort_index().astype(float)
    precios.index = pd.DatetimeIndex(precios.index)
    precios.index.name = "Fecha"

    if precios.empty:
        raise ValueError("No quedaron precios válidos.")

    # Crear calendario semanal completo.
    calendario = pd.date_range(
        precios.index.min(),
        precios.index.max(),
        freq="7D"
    )

    precios = precios.reindex(calendario)
    precios.index.name = "Fecha"

    faltantes = int(precios.isna().sum())

    if faltantes:
        print(f"\nSemanas sin precio observado: {faltantes}")
        print(
            "Se interpolarán únicamente los huecos interiores. "
            "Los valores interpolados no son observaciones reales."
        )

        precios = precios.interpolate(
            method="time",
            limit_area="inside"
        )

        if precios.isna().any():
            raise ValueError(
                "Hay semanas sin datos en los extremos de la serie. "
                "Revisa las fechas o limita el período de análisis."
            )

    print("\nDatos preparados")
    print(f"Producto: {PRODUCTO_OBJETIVO}")
    print(f"Mercado: {MERCADO_OBJETIVO}")
    print(f"Semanas: {len(precios)}")
    print(f"Desde: {precios.index.min().date()}")
    print(f"Hasta: {precios.index.max().date()}")

    if len(precios) < MINIMO_SEMANAS:
        raise ValueError(
            f"Solo hay {len(precios)} semanas; "
            f"se requieren al menos {MINIMO_SEMANAS}."
        )

    return precios


# ==========================================================
# VARIABLES PREDICTORAS
# ==========================================================

def crear_variables(serie):
    datos = pd.DataFrame(index=serie.index)

    datos["precio_actual"] = serie

    for lag in range(1, 4):
        datos[f"rezago_{lag}"] = serie.shift(lag)

    datos["media_4_semanas"] = serie.rolling(4).mean()

    # Precio de la semana siguiente.
    datos["objetivo"] = serie.shift(-1)

    return datos.dropna()


# ==========================================================
# MÉTRICAS DE EVALUACIÓN
# ==========================================================

def evaluar_modelo(real, predicho):
    return {
        "MAE": float(mean_absolute_error(real, predicho)),
        "RMSE": float(
            np.sqrt(mean_squared_error(real, predicho))
        ),
        "R2": (
            float(r2_score(real, predicho))
            if len(real) >= 2
            else np.nan
        ),
    }


# ==========================================================
# ENTRENAMIENTO Y COMPARACIÓN
# ==========================================================

def entrenar_y_evaluar():
    precios = cargar_datos()
    datos = crear_variables(precios)

    corte = int(len(datos) * PORCENTAJE_ENTRENAMIENTO)

    entrenamiento = datos.iloc[:corte].copy()
    prueba = datos.iloc[corte:].copy()

    if len(entrenamiento) < 10 or len(prueba) < 4:
        raise ValueError(
            "No hay suficientes registros para entrenar y evaluar. "
            "Reúne más semanas de datos."
        )

    X_train = entrenamiento[COLUMNAS_MODELO]
    y_train = entrenamiento["objetivo"]

    X_test = prueba[COLUMNAS_MODELO]
    y_test = prueba["objetivo"]

    modelos = {
        "Regresion Lineal": LinearRegression(),

        "Random Forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        ),

        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.05,
            max_depth=2,
            loss="squared_error",
            random_state=42
        ),
    }

    resultados = []
    modelos_entrenados = {}

    print("\n" + "=" * 65)
    print("COMPARACIÓN DE MODELOS DE PREDICCIÓN")
    print("=" * 65)

    print(f"Observaciones de entrenamiento: {len(entrenamiento)}")
    print(f"Observaciones de prueba: {len(prueba)}")
    print(f"Período de prueba: {prueba.index.min().date()} "
          f"a {prueba.index.max().date()}")

    for nombre, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        predicciones = modelo.predict(X_test)

        metricas = evaluar_modelo(y_test, predicciones)

        resultados.append({
            "Modelo": nombre,
            **metricas
        })

        modelos_entrenados[nombre] = modelo

        print(f"\n{nombre}")
        print(f"  MAE:  {metricas['MAE']:.2f} COP/kg")
        print(f"  RMSE: {metricas['RMSE']:.2f} COP/kg")
        print(f"  R²:   {metricas['R2']:.4f}")

    tabla = pd.DataFrame(resultados)

    # Menor MAE es mejor; el R² se informa como métrica adicional.
    tabla = tabla.sort_values(
        by=["MAE", "RMSE"],
        ascending=[True, True]
    ).reset_index(drop=True)

    print("\n" + "=" * 65)
    print("RESULTADOS ORDENADOS POR MAE Y RMSE")
    print("=" * 65)
    print(tabla.to_string(index=False))

    DIRECTORIO_MODELOS.mkdir(
        parents=True,
        exist_ok=True
    )

    tabla.to_csv(
        ARCHIVO_RESULTADOS,
        index=False,
        encoding="utf-8-sig"
    )

    # Elegir el ganador de esta comparación.
    ganador = tabla.iloc[0]["Modelo"]
    modelo_final = modelos_entrenados[ganador]

    # Reentrenar el ganador con todos los datos etiquetados disponibles.
    # La evaluación anterior se conserva como referencia de prueba.
    datos_completos = crear_variables(precios)

    modelo_final.fit(
        datos_completos[COLUMNAS_MODELO],
        datos_completos["objetivo"]
    )

    # Preparar las variables de la última semana para predecir la siguiente.
    ultima_fila = crear_variables(precios).iloc[-1]
    X_ultima = ultima_fila[COLUMNAS_MODELO].to_frame().T

    prediccion = float(modelo_final.predict(X_ultima)[0])
    fecha_prediccion = precios.index[-1] + pd.Timedelta(days=7)

    artefacto = {
        "modelo": modelo_final,
        "tipo": ganador,
        "producto": PRODUCTO_OBJETIVO,
        "mercado": MERCADO_OBJETIVO,
        "unidad": "COP/kg",
        "frecuencia": "semanal",
        "columnas": COLUMNAS_MODELO,
        "ultima_fecha": str(precios.index[-1].date()),
        "ultima_prediccion": prediccion,
        "fecha_prediccion": str(fecha_prediccion.date()),
        "metricas_prueba": tabla.iloc[0].to_dict(),
        "comparacion": tabla.to_dict(orient="records"),
        "semanas": int(len(precios)),
    }

    joblib.dump(artefacto, ARCHIVO_MODELO)

    print("\n" + "=" * 65)
    print(f"Modelo seleccionado: {ganador}")
    print(f"Predicción para: {fecha_prediccion.date()}")
    print(f"Precio estimado: {prediccion:.2f} COP/kg")
    print(f"Modelo guardado en: {ARCHIVO_MODELO}")
    print(f"Comparación guardada en: {ARCHIVO_RESULTADOS}")
    print(
        "\nNota: las métricas son de una única partición temporal. "
        "Para una evaluación académica robusta, realiza validación "
        "temporal adicional y compara con un modelo de persistencia."
    )


if __name__ == "__main__":
    entrenar_y_evaluar()
