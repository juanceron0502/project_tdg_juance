import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
SALIDA = BASE / "datos_limpios"

df = pd.read_csv(SALIDA / "popayan_mensual.csv", parse_dates=["fecha"])
df["mes"] = df["fecha"].dt.to_period("M")
print("Filas duplicadas (producto, mes):", df.duplicated(["producto", "mes"]).sum())

CANDIDATOS = ["Papa parda pastusa", "Tomate larga vida", "Habichuela",
              "Lulo", "Cebolla junca pastusa"]
TODOS = pd.period_range("2013-01", "2024-12", freq="M")

series = {}
for p in CANDIDATOS:
    s = df[df["producto"] == p].groupby("mes")["precio"].mean().reindex(TODOS)
    series[p] = s
    print("\n" + "=" * 60)
    print(p)
    print("Meses faltantes:", int(s.isna().sum()), list(s[s.isna()].index.astype(str)))
    print("Mediana por año:")
    print(s.groupby(s.index.year).median().round(0).to_string())
    saltos = s.pct_change(fill_method=None).abs().nlargest(3)
    print("Mayores saltos mes a mes:")
    for mes, v in saltos.items():
        print("  ", mes, f"{v:.0%}")

# ¿Existen naranja y café en el SIPSA de Popayán, aunque tengan menos cobertura?
cob = pd.read_csv(SALIDA / "cobertura_productos.csv")
print("\n", cob[cob["producto"].str.contains("naranja|café|cafe", case=False, na=False)]
      .to_string())

# Gráfico (necesita: pip install matplotlib)
try:
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(len(series), 1, figsize=(10, 2.6 * len(series)), sharex=True)
    for ax, (p, s) in zip(axs, series.items()):
        s.index = s.index.to_timestamp()
        ax.plot(s.index, s.values)
        ax.set_title(p, fontsize=10)
    plt.tight_layout()
    plt.savefig(SALIDA / "series_candidatas.png", dpi=120)
    print("\nGráfico guardado en", SALIDA / "series_candidatas.png")
except ImportError:
    print("\nInstala matplotlib para el gráfico: pip install matplotlib")