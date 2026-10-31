import sys, datetime as dt
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
rows = [l.split(" ", 2) for l in open(sys.argv[1]).read().splitlines() if l.strip()]
names = sorted({r[0] for r in rows}, key=lambda n: min(dt.datetime.strptime(s.split("–")[0].strip(), "%H:%M:%S") for r in rows if r[0] == n for s in r[2].split(";")))
fig, ax = plt.subplots(figsize=(10, 3.6)); fig.patch.set_facecolor("#fcfcfb"); ax.set_facecolor("#fcfcfb")
C = {"pending": "#eda100", "firing": "#d03b3b"}
for n, st, segs in rows:
    y = names.index(n)
    for s in segs.split(";"):
        a, b = [dt.datetime.strptime(x.strip(), "%H:%M:%S") for x in s.split("–")]
        ax.barh(y, max((b - a).total_seconds() / 60, 0.25), left=(a.hour * 60 + a.minute + a.second / 60), height=0.5, color=C[st], edgecolor="#fcfcfb", linewidth=1)
ax.set_yticks(range(len(names))); ax.set_yticklabels(names, fontsize=9, color="#0b0b0b")
t = ax.get_xticks(); ax.set_xticklabels([f"{int(v//60):02d}:{int(v%60):02d}" for v in t], color="#52514e")
for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
ax.grid(axis="x", color="#e6e5e1"); ax.set_axisbelow(True)
ax.set_title("Alertas de RedAlimenta durante las pruebas (hora local): pendiente → activa → resuelta", loc="left", fontsize=11)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=C["pending"], label="pending (umbral sin cumplir duración)"), Patch(color=C["firing"], label="firing (activa)")], frameon=False, loc="lower right", fontsize=8)
plt.tight_layout(); plt.savefig(sys.argv[2], dpi=150); print("ok")
