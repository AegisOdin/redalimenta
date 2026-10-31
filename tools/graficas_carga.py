"""Gráficas del experimento HPA (PNG para el informe). Uso: graficas_carga.py <dir_carga>"""
import csv, sys, datetime as dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

D = sys.argv[1]
CON = sys.argv[2] if len(sys.argv) > 2 else "serie-con-hpa.csv"
AZUL, NARANJA, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURF, TXT, TXT2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": TXT2,
                     "xtick.color": TXT2, "ytick.color": TXT2, "axes.facecolor": SURF, "figure.facecolor": SURF,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False})

def leer(n):
    rows = list(csv.DictReader(open(f"{D}/{n}")))
    t0 = dt.datetime.fromisoformat(rows[0]["ts"])
    f = lambda k: [float(r[k]) if r[k] not in ("", "nan") else float("nan") for r in rows]
    return [(dt.datetime.fromisoformat(r["ts"]) - t0).total_seconds() / 60 for r in rows], f, rows

def fin(ax, titulo, ylab, nombre):
    ax.set_title(titulo, loc="left", color=TXT, fontsize=12, pad=12); ax.set_xlabel("minutos desde el inicio (línea base 0-5, rampa 5-17)"); ax.set_ylabel(ylab)
    ax.axvspan(5, 17, color="#f1f0ec", zorder=0); ax.legend(frameon=False, loc="upper left")
    plt.tight_layout(); plt.savefig(f"{D}/{nombre}", dpi=150); plt.close()

xa, fa, _ = leer("serie-con-hpa-intento1-pending.csv") if __import__("os").path.exists(f"{D}/serie-con-hpa-intento1-pending.csv") else (None, None, None)
if xa:
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.step(xa, fa("hpa_deseadas"), where="post", color=AZUL, lw=2, label="réplicas deseadas (HPA)")
    ax.step(xa, fa("ready"), where="post", color=NARANJA, lw=2, label="réplicas Ready (4 en Pending)")
    ax.set_ylim(0, 7)
    fin(ax, "Intento 1: el HPA pide 6 réplicas pero solo 2 se programan", "réplicas", "g0-intento1-pending.png")
x, f, _ = leer(CON)
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.step(x, f("hpa_deseadas"), where="post", color=AZUL, lw=6, alpha=0.45, label="réplicas deseadas (HPA)")
ax.step(x, f("ready"), where="post", color=NARANJA, lw=2, label="réplicas Ready (coinciden: sin Pending)")
ax.set_ylim(0, 7); ax.set_yticks(range(0, 8))
fin(ax, "HPA del backend: réplicas deseadas y Ready (min 2, max 6)", "réplicas", "g1-replicas-hpa.png")

fig, ax = plt.subplots(figsize=(9, 3.8))
ax.plot(x, f("cpu_hpa_pct"), color=AZUL, lw=2, label="CPU promedio vs requests (%)")
ax.axhline(60, color=TXT2, lw=1, ls="--"); ax.text(x[-1], 62, "objetivo 60 %", ha="right", color=TXT2, fontsize=9)
fin(ax, "Utilización de CPU observada por el HPA", "% de requests (250m)", "g2-cpu-hpa.png")

xs, fs, _ = leer("serie-sin-hpa.csv")
for k, tit, yl, n, esc in (("rps", "Solicitudes por segundo atendidas (mismo escenario)", "req/s", "g3-rps-comparacion.png", 1),
                           ("p95_s", "Latencia p95 del backend (mismo escenario)", "ms", "g4-p95-comparacion.png", 1000)):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(x, [v * esc for v in f(k)], color=AZUL, lw=2, label="con HPA (2→6 réplicas)")
    ax.plot(xs, [v * esc for v in fs(k)], color=NARANJA, lw=2, label="sin HPA (2 réplicas fijas)")
    fin(ax, tit, yl, n)
print("ok")
