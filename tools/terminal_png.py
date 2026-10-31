"""Renderiza una salida de texto como captura de terminal (PNG). Uso: terminal_png.py <txt> <png> <titulo> [max_lineas] [desde_linea]"""
import sys, textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
src, out, titulo = sys.argv[1:4]
maxl = int(sys.argv[4]) if len(sys.argv) > 4 else 46
desde = int(sys.argv[5]) if len(sys.argv) > 5 else 0
lines = []
import re
for l in re.sub(r"\x1b\[[0-9;]*m", "", open(src, encoding="utf-8", errors="replace").read()).splitlines()[desde:]:
    lines += textwrap.wrap(l.expandtabs(4), 128, replace_whitespace=False, drop_whitespace=False) or [""]
if len(lines) > maxl:
    lines = lines[:maxl - 1] + [f"… ({len(lines) - maxl + 1} líneas más en {src.split('/')[-1]})"]
h = 0.62 + 0.17 * len(lines)
fig = plt.figure(figsize=(13, h), dpi=130); fig.patch.set_facecolor("#1e1f1c")
ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, h)
ax.add_patch(plt.Rectangle((0, h - 0.38), 1, 0.38, color="#33342f"))
ax.text(0.5, h - 0.19, titulo, color="#d6d5cf", ha="center", va="center", fontsize=10, family="DejaVu Sans")
for i, l in enumerate(lines):
    col = "#e8e6df"
    if l.startswith(("==", "#")): col = "#7fd1a8"
    elif any(k in l for k in ("BLOQUEAD", "SIN RESPUESTA", "ERROR", "Forbidden", "no ", "rechazado", "MongoServerError")): col = "#f2a37b"
    ax.text(0.012, h - 0.55 - i * 0.17, l, color=col, family="DejaVu Sans Mono", fontsize=8.6, va="center")
fig.savefig(out, facecolor=fig.get_facecolor()); print("ok", out, len(lines))
