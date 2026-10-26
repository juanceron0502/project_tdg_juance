import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent   # en Jupyter/Colab: Path.cwd()
ARCHIVO_CSV = BASE_DIR / "datos" / "papa_semanal.csv"
DIRECTORIO_MODELOS = BASE_DIR / "modelos"
DIRECTORIO_MODELOS.mkdir(exist_ok=True)
ARCHIVO_MODELO = DIRECTORIO_MODELOS / "papa_semanal.joblib"
ARCHIVO_RESULTADOS = DIRECTORIO_MODELOS / "comparacion_modelos.csv"

FRECUENCIA = "W"          # "W" = semanal, "M" = mensual
PRODUCTO = None           # lo defines después de ver el inventario

COLUMNAS = {
    "Fecha": "fecha",
    "Grupo": "grupo",
    "Producto": "producto",
    "CODIGO_CPC_AC": "cpc",
    "Mercado": "mercado",
    "Precio promedio por kilogramo*": "precio",
}

# 1. Lectura (si salen tildes raras, cambia encoding a "latin-1")
df = pd.read_csv(ARCHIVO_CSV, sep=";", encoding="utf-8", decimal=",")
df = df.rename(columns=COLUMNAS)
print(df.shape)
print(df.head())
print(df.dtypes)

# 2. Tipos
df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
print("Fechas inválidas:", df["fecha"].isna().sum(),
      "| Precios inválidos:", df["precio"].isna().sum())

# 3. Solo Popayán
print(df["mercado"].unique())
df = df[df["mercado"].str.contains("Popay", case=False, na=False)]
df["periodo"] = df["fecha"].dt.to_period(FRECUENCIA)

# 4. Inventario: períodos con datos por producto
inv = (df.groupby(["cpc", "producto"])["periodo"]
         .nunique()
         .sort_values(ascending=False))
print(inv.head(25))

# 5. Serie de un producto (define PRODUCTO con el nombre exacto del inventario)
if PRODUCTO:
    s = (df[df["producto"] == PRODUCTO]
           .groupby("periodo")["precio"].mean())
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq=FRECUENCIA))
    print(s.isna().sum(), "períodos faltantes de", len(s))
    print(s.describe())