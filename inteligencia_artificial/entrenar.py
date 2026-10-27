import warnings
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parent
SALIDA = BASE / "datos_limpios"
MODELOS = BASE / "modelos"
MODELOS.mkdir(exist_ok=True)

PRODUCTOS = ["Papa parda pastusa", "Tomate larga vida", "Habichuela"]
INICIO_PRUEBA = pd.Period("2023-01", "M")     # primer mes que se predice
SEMILLA = 42

MODELOS_SK = {
    "Regresión Lineal": lambda: LinearRegression(),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=300, min_samples_leaf=3, random_state=SEMILLA, n_jobs=-1),
    "Gradient Boosting": lambda: GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.05, max_depth=2,
        subsample=0.8, random_state=SEMILLA),
}

df = pd.read_csv(SALIDA / "popayan_mensual.csv", parse_dates=["fecha"])
df["mes"] = df["fecha"].dt.to_period("M")


def serie_mensual(producto):
    s = df[df["producto"] == producto].groupby("mes")["precio"].mean()
    s = s.reindex(pd.period_range(s.index.min(), "2024-12", freq="M"))
    faltantes = int(s.isna().sum())
    s = np.exp(np.log(s).interpolate(method="linear"))    # interpolar en log
    return s, faltantes


def construir(s):
    """Variables conocidas en el mes t para predecir el mes t+1."""
    y = np.log(s)
    d = y.diff()
    X = pd.DataFrame(index=s.index)
    X["d_lag0"] = d                          # variación del mes t-1 al t
    X["d_lag1"] = d.shift(1)
    X["d_lag2"] = d.shift(2)
    X["gap_ma3"] = y - y.rolling(3).mean()   # distancia a la media de 3 meses
    X["gap_ma12"] = y - y.rolling(12).mean() # distancia a la media anual
    mes_obj = np.asarray((s.index + 1).month)    # mes que se va a predecir
    X["mes_sin"] = np.sin(2 * np.pi * mes_obj / 12)
    X["mes_cos"] = np.cos(2 * np.pi * mes_obj / 12)
    objetivo = y.shift(-1) - y               # variación hacia t+1
    return X, objetivo


def evaluar(producto):
    s, faltantes = serie_mensual(producto)
    X, y = construir(s)
    datos = X.copy()
    datos["y"] = y
    datos = datos.dropna()
    cols = list(X.columns)

    t_prueba = [t for t in datos.index if t + 1 >= INICIO_PRUEBA]
    nombres = ["Ingenuo (mes anterior)", "Ingenuo estacional (12 meses)"] + list(MODELOS_SK)
    preds = {n: [] for n in nombres}
    reales = []

    for t in t_prueba:
        # Walk-forward: solo se entrena con objetivos ya conocidos al llegar a t
        entren = datos[datos.index + 1 <= t]
        precio_t = s.loc[t]
        reales.append(s.loc[t + 1])
        preds["Ingenuo (mes anterior)"].append(precio_t)
        preds["Ingenuo estacional (12 meses)"].append(s.loc[t + 1 - 12])
        for nombre, f in MODELOS_SK.items():
            m = f().fit(entren[cols], entren["y"])
            d_hat = m.predict(datos.loc[[t], cols])[0]
            preds[nombre].append(precio_t * np.exp(d_hat))

    reales = np.array(reales)
    filas = []
    for nombre, p in preds.items():
        p = np.array(p)
        filas.append({
            "producto": producto,
            "modelo": nombre,
            "MAE": mean_absolute_error(reales, p),
            "RMSE": np.sqrt(mean_squared_error(reales, p)),
            "R2": r2_score(reales, p),
        })
    tabla = pd.DataFrame(filas).set_index("modelo")
    rmse_ing = tabla.loc["Ingenuo (mes anterior)", "RMSE"]
    tabla["mejora_RMSE_vs_ingenuo_%"] = (rmse_ing - tabla["RMSE"]) / rmse_ing * 100

    print("\n" + "=" * 70)
    print(f"{producto} | meses interpolados: {faltantes} | "
          f"entrenamiento inicial: {len(datos) - len(t_prueba)} | meses de prueba: {len(t_prueba)}")
    print(tabla.round(2).to_string())

    # Modelo final: el mejor de los tres de ML, reentrenado con todos los datos
    mejor = min(MODELOS_SK, key=lambda n: tabla.loc[n, "RMSE"])
    final = MODELOS_SK[mejor]().fit(datos[cols], datos["y"])
    archivo = MODELOS / (producto.lower().replace(" ", "_") + ".joblib")
    joblib.dump({"modelo": final, "modelo_nombre": mejor, "columnas": cols,
                 "producto": producto, "ultimo_mes": str(s.index[-1])}, archivo)
    print("Mejor modelo de ML:", mejor, "->", archivo.name)
    return tabla.reset_index()


resultados = pd.concat([evaluar(p) for p in PRODUCTOS], ignore_index=True)
resultados.to_csv(MODELOS / "comparacion_modelos.csv", index=False)
print("\nGuardado:", MODELOS / "comparacion_modelos.csv")