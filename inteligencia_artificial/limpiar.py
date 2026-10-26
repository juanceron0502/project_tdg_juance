import re
import zipfile
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATOS = BASE / "datos"
EXTRAIDO = DATOS / "extraido"
SALIDA = BASE / "datos_limpios"
EXTRAIDO.mkdir(exist_ok=True)
SALIDA.mkdir(exist_ok=True)

for z in sorted(DATOS.glob("*.zip")):
    with zipfile.ZipFile(z) as f:
        f.extractall(EXTRAIDO / z.stem)

csvs = sorted(EXTRAIDO.rglob("*.csv"))
print("CSV a leer:", len(csvs))

# ---------- utilidades ----------
def norm(c):
    return str(c).strip().lower().replace("*", "").replace("_", " ").strip()

MAPA = {
    "fecha": "fecha", "grupo": "grupo", "producto": "producto",
    "codigo cpc ac": "cpc", "cpc": "cpc",
    "mercado": "mercado", "fuente": "mercado",
    "precio": "precio",
    "precio por kilogramo": "precio",
    "precio promedio por kilogramo": "precio",
}

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
         "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12}

def parse_una(x):
    s = str(x).strip().lower()
    m = re.fullmatch(r"([a-záéíóú]{3,4})[-/ ](\d{2,4})", s)      # "ene-22"
    if m and m.group(1) in MESES:
        anio = int(m.group(2))
        if anio < 100:
            anio += 2000
        return pd.Timestamp(anio, MESES[m.group(1)], 1)
    return pd.to_datetime(s, dayfirst=True, errors="coerce")    # "1/01/2013"

def parse_fechas(serie):
    mapa = {u: parse_una(u) for u in serie.dropna().unique()}
    return pd.to_datetime(serie.map(mapa))

def limpiar_precio(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype(float)
    s = serie.astype(str).str.strip().str.replace(r"[^\d,.\-]", "", regex=True)
    s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)  # "1.150" -> 1150
    return pd.to_numeric(s, errors="coerce")

def leer_csv(a):
    for enc in ("utf-8", "latin-1"):
        try:
            d = pd.read_csv(a, sep=";", encoding=enc, dtype=str)
            if d.shape[1] == 1:
                d = pd.read_csv(a, sep=",", encoding=enc, dtype=str)
            return d
        except UnicodeDecodeError:
            continue
    raise ValueError(f"No pude leer {a}")

# ---------- lectura ----------
partes = []
for a in csvs:
    d = leer_csv(a)
    d.columns = [norm(c) for c in d.columns]
    d = d.rename(columns=MAPA)
    d = d.loc[:, ~d.columns.duplicated()]
    if not {"fecha", "producto", "mercado", "precio"} <= set(d.columns):
        print(f"\n{a.name}: OJO faltan columnas | tiene: {list(d.columns)}")
        continue
    for extra in ("cpc", "grupo"):
        if extra not in d.columns:
            d[extra] = pd.NA

    d = d[d["mercado"].astype(str).str.contains("Popay", case=False, na=False)].copy()
    d["fecha"] = parse_fechas(d["fecha"])
    d["precio"] = limpiar_precio(d["precio"])
    d = d[["fecha", "grupo", "producto", "cpc", "mercado", "precio"]]
    d["archivo"] = a.name

    print(f"\n{a.name}: {len(d)} filas de Popayán")
    print("   fechas sin interpretar:", d["fecha"].isna().sum(),
          "| rango:", d["fecha"].min().date() if d["fecha"].notna().any() else None,
          "→", d["fecha"].max().date() if d["fecha"].notna().any() else None)
    print("   precio: mediana =", d["precio"].median(),
          "| nulos =", d["precio"].isna().sum())
    partes.append(d)

df = pd.concat(partes, ignore_index=True)
df = df.dropna(subset=["fecha", "precio"]).copy()
df["producto"] = df["producto"].astype(str).str.strip()
df["mes"] = df["fecha"].dt.to_period("M")

# ---------- controles ----------
meses_esperados = len(pd.period_range(df["mes"].min(), df["mes"].max(), freq="M"))
print("\nRango total:", df["mes"].min(), "→", df["mes"].max(),
      "| meses esperados:", meses_esperados, "| meses con datos:", df["mes"].nunique())
print("Filas duplicadas (producto, mes):", df.duplicated(["producto", "mes"]).sum())
print("\nGrupos de producto:\n", df["grupo"].value_counts().to_string())

# ---------- cobertura ----------
cobertura = (df.groupby("producto")
               .agg(grupo=("grupo", "first"),
                    meses=("mes", "nunique"),
                    primer_mes=("mes", "min"),
                    ultimo_mes=("mes", "max"),
                    precio_min=("precio", "min"),
                    precio_mediana=("precio", "median"),
                    precio_max=("precio", "max"))
               .sort_values("meses", ascending=False))
cobertura["pct_meses"] = (cobertura["meses"] / meses_esperados * 100).round(1)

print("\nProductos con >= 90 % de los meses:")
print(cobertura[cobertura["pct_meses"] >= 90].to_string())

df.to_csv(SALIDA / "popayan_mensual.csv", index=False)
cobertura.to_csv(SALIDA / "cobertura_productos.csv")
print("\nGuardado en:", SALIDA)