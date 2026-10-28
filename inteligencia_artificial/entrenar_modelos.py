"""
entrenar_modelos.py  -  Tierra de Grandes
Compara modelos de estimación del precio mayorista (SIPSA, Popayán) y genera,
para cada producto, una recomendación en lenguaje sencillo para el agricultor.

Entradas : datos_limpios/popayan_mensual.csv  (salida de limpiar.py)
Salidas  : modelos/<producto>.joblib      modelo + parámetros de la recomendación
           modelos/comparacion_modelos.csv  métricas por producto y modelo
           modelos/recomendaciones.json     para la plataforma (Django)
           modelos/recomendaciones.csv      lectura rápida
           modelos/pred_<producto>.csv      predicciones vs. reales
"""
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SALIDA = BASE / "datos_limpios"
MODELOS = BASE / "modelos"
MODELOS.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------
# CONFIGURACIÓN (todo lo que decide el criterio de éxito queda aquí, a la vista)
# ----------------------------------------------------------------------------
PRODUCTOS = ["Papa parda pastusa", "Tomate larga vida", "Habichuela"]
USAR_TODOS_FRESCOS = False          # True: todos los frescos con >= 95 % de cobertura
FIN_DATOS = "2024-12"
INICIO_VALIDACION = pd.Period("2021-01", "M")   # 2021-2022: se ELIGE el método
INICIO_PRUEBA = pd.Period("2023-01", "M")       # 2023-2024: se REPORTA el resultado
SEMILLA = 42

UMBRAL_ESTABLE = 0.03       # cambios menores a +-3 % se consideran "estable"
MEJORA_MEDIA = 0.03         # mejora mínima de RMSE vs. ingenuo para usar el modelo
MEJORA_ALTA = 0.10          # mejora para confianza alta (junto con p < P_ALTA)
P_ALTA = 0.05
ACIERTO_ALTA = 0.60         # acierto de dirección exigido para confianza alta
CONSISTENCIA_MIN = 0.70     # % de años en que un mes debe repetir su patrón

NAIVE = "Ingenuo (mes anterior)"
ESTAC = "Ingenuo estacional (12 meses)"      # solo referencia, no es elegible

METODOS_ML = {
    "Regresión Lineal": lambda: LinearRegression(),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=300, min_samples_leaf=3, random_state=SEMILLA, n_jobs=-1),
    "Gradient Boosting": lambda: GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=2,
        subsample=0.8, random_state=SEMILLA),
}
ELEGIBLES = [NAIVE] + list(METODOS_ML)

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ----------------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------------
def rmse(a, b):
    return float(np.sqrt(mean_squared_error(a, b)))


def cop(x):
    """1234.5 -> '$1.235' (formato colombiano)."""
    return "$" + f"{x:,.0f}".replace(",", ".")


def pct(x, signo=False):
    f = f"{x * 100:+.0f} %" if signo else f"{x * 100:.0f} %"
    return f


def nombre_mes(periodo):
    return f"{MESES_ES[periodo.month - 1]} de {periodo.year}"


def limpio(v):
    """Convierte tipos numpy y NaN a algo que JSON acepte."""
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def slug(nombre):
    return nombre.lower().replace(" ", "_").replace(",", "")


# ----------------------------------------------------------------------------
# SERIE Y VARIABLES
# ----------------------------------------------------------------------------
def serie_mensual(df, producto):
    s = df[df["producto"] == producto].groupby("mes")["precio"].mean()
    s = s.reindex(pd.period_range(s.index.min(), FIN_DATOS, freq="M"))
    faltantes = int(s.isna().sum())
    s = np.exp(np.log(s).interpolate(method="linear"))      # interpolación en log
    return s, faltantes


def construir(s):
    """Variables conocidas en el mes t para estimar el cambio hacia t+1."""
    y = np.log(s)
    d = y.diff()
    X = pd.DataFrame(index=s.index)
    X["d_lag0"] = d
    X["d_lag1"] = d.shift(1)
    X["d_lag2"] = d.shift(2)
    X["gap_ma3"] = y - y.rolling(3).mean()
    X["gap_ma12"] = y - y.rolling(12).mean()
    mes_obj = np.asarray((s.index + 1).month)
    X["mes_sin"] = np.sin(2 * np.pi * mes_obj / 12)
    X["mes_cos"] = np.cos(2 * np.pi * mes_obj / 12)
    objetivo = y.shift(-1) - y
    return X, objetivo


# ----------------------------------------------------------------------------
# VALIDACIÓN WALK-FORWARD
# ----------------------------------------------------------------------------
def walk_forward(s, datos, cols, inicio):
    """Estima mes a mes reentrenando solo con lo que se conocía en ese momento."""
    filas = {}
    for t in [t for t in datos.index if t + 1 >= inicio]:
        entren = datos[(datos.index + 1) <= t]
        fila = {"real": s.loc[t + 1], "precio_t": s.loc[t],
                NAIVE: s.loc[t], ESTAC: s.loc[t + 1 - 12]}
        xt = datos.loc[[t], cols]
        for nombre, fabrica in METODOS_ML.items():
            m = fabrica().fit(entren[cols], entren["y"])
            fila[nombre] = s.loc[t] * np.exp(m.predict(xt)[0])
        filas[t + 1] = fila
    out = pd.DataFrame.from_dict(filas, orient="index")
    out.index = pd.PeriodIndex(out.index, freq="M")
    return out


# ----------------------------------------------------------------------------
# ESTACIONALIDAD (qué meses suelen tener precios altos o bajos)
# ----------------------------------------------------------------------------
def estacionalidad(s):
    y = np.log(s)
    desv = (y - y.rolling(12, center=True).mean()).dropna()   # sin efecto de la inflación
    g = desv.groupby(desv.index.month)
    tabla = pd.DataFrame({
        "desvio": np.exp(g.mean()) - 1,
        "sobre_media": g.apply(lambda x: (x > 0).mean()),     # % de años por encima de su media
    })
    altos = tabla.sort_values("desvio", ascending=False).head(3)
    bajos = tabla.sort_values("desvio").head(3)
    conf_altos = bool((altos["sobre_media"] >= CONSISTENCIA_MIN).all())
    conf_bajos = bool(((1 - bajos["sobre_media"]) >= CONSISTENCIA_MIN).all())
    return altos, bajos, conf_altos, conf_bajos


def lista_meses(tabla):
    return ", ".join(MESES_ES[m - 1] for m in sorted(tabla.index))


# ----------------------------------------------------------------------------
# RECOMENDACIÓN PARA EL AGRICULTOR  (esta función se reutiliza en Django)
# ----------------------------------------------------------------------------
def generar_recomendacion(b, s):
    """b: paquete guardado en .joblib | s: serie mensual de precios actualizada."""
    t = s.index[-1]
    objetivo = t + 1
    precio_act = float(s.iloc[-1])

    if b["metodo"] == NAIVE:
        est = precio_act
    else:
        X, _ = construir(s)
        d_hat = b["modelo"].predict(X.loc[[t], b["columnas"]])[0]
        est = precio_act * float(np.exp(d_hat))

    lo, hi = est * float(np.exp(b["q_lo"])), est * float(np.exp(b["q_hi"]))
    cambio = est / precio_act - 1

    if b["metodo"] == NAIVE:
        direccion = "Sin señal"
    elif cambio > UMBRAL_ESTABLE:
        direccion = "Sube"
    elif cambio < -UMBRAL_ESTABLE:
        direccion = "Baja"
    else:
        direccion = "Estable"

    vs12 = precio_act / float(s.iloc[-12:].mean()) - 1
    altos, bajos, conf_altos, conf_bajos = estacionalidad(s)

    # ---- mensaje en lenguaje sencillo ----
    msg = []
    msg.append(
        f"Precio de referencia de {b['producto']} para {nombre_mes(objetivo)}: "
        f"{cop(est)} por kg (rango probable: {cop(lo)} a {cop(hi)}).")

    if direccion == "Sube":
        msg.append(f"Se espera que el precio suba cerca de {pct(cambio)} frente a "
                   f"{MESES_ES[t.month - 1]}.")
    elif direccion == "Baja":
        msg.append(f"Se espera que el precio baje cerca de {pct(abs(cambio))} frente a "
                   f"{MESES_ES[t.month - 1]}.")
    elif direccion == "Estable":
        msg.append("Se espera un precio parecido al del mes actual.")
    else:
        msg.append("Para este producto no hay una señal confiable de subida o bajada; "
                   "la referencia es el último precio observado.")

    if b["nivel"] == "Alta":
        msg.append(f"Confianza alta: en los últimos {b['meses_prueba']} meses el modelo "
                   f"redujo el error en {pct(b['mejora_rmse'])} frente a repetir el precio "
                   "del mes anterior.")
    elif b["nivel"] == "Media":
        msg.append(f"Confianza media: el modelo redujo el error en {pct(b['mejora_rmse'])} "
                   "frente al método simple, pero con pocos meses de prueba esa "
                   "diferencia no es concluyente. Úselo como guía, no como cifra exacta.")
    else:
        msg.append("Confianza baja: el modelo no superó a repetir el último precio, "
                   "por eso se usa el precio actual como referencia.")

    msg.append(f"El error típico de este método ha sido de unos {pct(b['error_tipico'])}.")

    if abs(vs12) >= 0.05:
        lado = "por encima" if vs12 > 0 else "por debajo"
        msg.append(f"El precio actual está {pct(abs(vs12))} {lado} del promedio de los "
                   "últimos 12 meses.")
    else:
        msg.append("El precio actual está cerca del promedio de los últimos 12 meses.")

    if conf_altos:
        msg.append(f"Históricamente los precios suelen ser más altos en {lista_meses(altos)}.")
    else:
        msg.append("No se observa una temporada de precios altos estable para este producto.")
    if conf_bajos:
        msg.append(f"Suelen ser más bajos en {lista_meses(bajos)}.")

    msg.append("Es una estimación del precio mayorista en Popayán (SIPSA-DANE), "
               "no un precio garantizado de venta.")

    return {
        "producto": b["producto"],
        "mes_base": str(t),
        "mes_estimado": str(objetivo),
        "precio_actual": round(precio_act),
        "precio_estimado": round(est),
        "rango_bajo": round(lo),
        "rango_alto": round(hi),
        "cambio_esperado_pct": round(cambio * 100, 1),
        "direccion": direccion,
        "confianza": b["nivel"],
        "metodo": b["metodo"],
        "mejora_vs_ingenuo_pct": round(b["mejora_rmse"] * 100, 1),
        "error_tipico_pct": round(b["error_tipico"] * 100, 1),
        "vs_promedio_12m_pct": round(vs12 * 100, 1),
        "meses_altos": [int(m) for m in altos.index] if conf_altos else [],
        "meses_bajos": [int(m) for m in bajos.index] if conf_bajos else [],
        "mensaje": msg,
    }


# ----------------------------------------------------------------------------
# EVALUACIÓN DE UN PRODUCTO
# ----------------------------------------------------------------------------
def evaluar_producto(df, producto):
    s, faltantes = serie_mensual(df, producto)
    X, y = construir(s)
    datos = X.assign(y=y).dropna()
    cols = list(X.columns)

    wf = walk_forward(s, datos, cols, INICIO_VALIDACION)
    val = wf[wf.index < INICIO_PRUEBA]
    prueba = wf[wf.index >= INICIO_PRUEBA]

    # 1) ELEGIR con validación (2021-2022)
    elegido = min(ELEGIBLES, key=lambda m: rmse(val["real"], val[m]))

    # 2) REPORTAR con prueba (2023-2024)
    rm_ing = rmse(prueba["real"], prueba[NAIVE])
    if elegido != NAIVE:
        rm_el = rmse(prueba["real"], prueba[elegido])
        mejora = (rm_ing - rm_el) / rm_ing
        e_ing = (prueba[NAIVE] - prueba["real"]) ** 2
        e_mod = (prueba[elegido] - prueba["real"]) ** 2
        p = float(stats.ttest_1samp(e_ing - e_mod, 0.0).pvalue)
    else:
        mejora, p = 0.0, np.nan

    # 3) Regla de decisión: si no mejora lo suficiente, se usa el último precio
    metodo = elegido if (elegido != NAIVE and mejora >= MEJORA_MEDIA) else NAIVE
    if metodo == NAIVE:
        mejora, p = 0.0, np.nan

    # 4) Acierto de dirección cuando el modelo avisa que sube o baja
    acierto, n_sen = np.nan, 0
    if metodo != NAIVE:
        c_pred = np.log(prueba[metodo] / prueba["precio_t"])
        c_real = np.log(prueba["real"] / prueba["precio_t"])
        sen = c_pred.abs() > UMBRAL_ESTABLE
        n_sen = int(sen.sum())
        if n_sen >= 5:
            acierto = float((np.sign(c_pred[sen]) == np.sign(c_real[sen])).mean())

    # 5) Nivel de confianza
    if metodo == NAIVE:
        nivel = "Baja"
    elif (mejora >= MEJORA_ALTA and p < P_ALTA
          and (np.isnan(acierto) or acierto >= ACIERTO_ALTA)):
        nivel = "Alta"
    else:
        nivel = "Media"

    # 6) Rango probable: cuantiles del error observado fuera de muestra (80 %)
    err = np.log(wf["real"] / wf[metodo])
    q_lo, q_hi = float(np.quantile(err, 0.10)), float(np.quantile(err, 0.90))
    error_tipico = float((wf["real"] / wf[metodo] - 1).abs().median())

    # 7) Modelo final con todos los datos
    modelo = None if metodo == NAIVE else METODOS_ML[metodo]().fit(datos[cols], datos["y"])

    bundle = {
        "producto": producto, "metodo": metodo, "modelo": modelo, "columnas": cols,
        "q_lo": q_lo, "q_hi": q_hi, "nivel": nivel, "mejora_rmse": float(mejora),
        "p_valor": p, "acierto_direccion": acierto, "n_senales": n_sen,
        "error_tipico": error_tipico, "meses_prueba": int(len(prueba)),
        "metodo_validacion": elegido, "datos_hasta": str(s.index[-1]),
    }
    joblib.dump(bundle, MODELOS / f"{slug(producto)}.joblib")
    wf.to_csv(MODELOS / f"pred_{slug(producto)}.csv")

    # tabla de métricas
    filas = []
    for nombre in [NAIVE, ESTAC] + list(METODOS_ML):
        for etapa, parte in (("validación 2021-22", val), ("prueba 2023-24", prueba)):
            filas.append({
                "producto": producto, "modelo": nombre, "etapa": etapa,
                "MAE": mean_absolute_error(parte["real"], parte[nombre]),
                "RMSE": rmse(parte["real"], parte[nombre]),
                "R2": r2_score(parte["real"], parte[nombre]),
                "elegido_en_validacion": nombre == elegido,
                "metodo_final": nombre == metodo,
            })
    tabla = pd.DataFrame(filas)

    rec = generar_recomendacion(bundle, s)
    rec["meses_interpolados"] = faltantes
    rec["p_valor"] = p
    rec["acierto_direccion_pct"] = None if np.isnan(acierto) else round(acierto * 100)
    rec["n_senales_direccion"] = n_sen
    return tabla, rec


# ----------------------------------------------------------------------------
# PROGRAMA PRINCIPAL
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    df = pd.read_csv(SALIDA / "popayan_mensual.csv", parse_dates=["fecha"])
    df["mes"] = df["fecha"].dt.to_period("M")

    if USAR_TODOS_FRESCOS:
        cob = pd.read_csv(SALIDA / "cobertura_productos.csv")
        frescos = ["FRUTAS", "VERDURAS Y HORTALIZAS", "TUBERCULOS, RAICES Y PLATANOS"]
        PRODUCTOS = cob[cob["grupo"].isin(frescos) & (cob["pct_meses"] >= 95)]["producto"].tolist()

    tablas, recs = [], []
    for i, prod in enumerate(PRODUCTOS, 1):
        print(f"[{i}/{len(PRODUCTOS)}] {prod} ...")
        t, r = evaluar_producto(df, prod)
        tablas.append(t)
        recs.append(r)

    comparacion = pd.concat(tablas, ignore_index=True)
    comparacion.to_csv(MODELOS / "comparacion_modelos.csv", index=False)

    with open(MODELOS / "recomendaciones.json", "w", encoding="utf-8") as f:
        json.dump([{k: limpio(v) for k, v in r.items()} for r in recs],
                  f, ensure_ascii=False, indent=2)

    resumen = pd.DataFrame([{k: v for k, v in r.items() if k != "mensaje"} for r in recs])
    resumen.to_csv(MODELOS / "recomendaciones.csv", index=False, encoding="utf-8-sig")

    # ---- informe en consola ----
    print("\n" + "=" * 72)
    print("RESULTADOS EN LA PRUEBA 2023-2024 (RMSE en pesos/kg)")
    print("=" * 72)
    pr = comparacion[comparacion["etapa"] == "prueba 2023-24"]
    for prod, g in pr.groupby("producto", sort=False):
        ing = g.loc[g["modelo"] == NAIVE, "RMSE"].iloc[0]
        g = g.assign(mejora_vs_ingenuo_pct=(ing - g["RMSE"]) / ing * 100)
        print(f"\n{prod}")
        print(g[["modelo", "MAE", "RMSE", "R2", "mejora_vs_ingenuo_pct",
                 "elegido_en_validacion", "metodo_final"]].round(2).to_string(index=False))

    print("\n" + "=" * 72)
    print("RECOMENDACIONES PARA EL AGRICULTOR")
    print("=" * 72)
    for r in recs:
        print(f"\n--- {r['producto']}  |  confianza: {r['confianza']}  |  método: {r['metodo']}")
        for linea in r["mensaje"]:
            print("  •", linea)

    print("\nArchivos guardados en:", MODELOS)