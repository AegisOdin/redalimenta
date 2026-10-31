#!/usr/bin/env python3
"""Resume un CSV de la sonda: total, errores, primer/último error y ventana sin servicio."""
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
err = [r for r in rows if r["status"] != "200"]
lat = sorted(int(r["ms"]) for r in rows if r["status"] == "200")
p95 = lat[int(len(lat) * 0.95) - 1] if lat else 0
print(f"solicitudes={len(rows)} correctas={len(rows)-len(err)} fallidas={len(err)} ({100*len(err)/max(1,len(rows)):.2f}%) p95_ok={p95} ms")
if err:
    print(f"primer error {err[0]['ts']} (HTTP {err[0]['status']}), último error {err[-1]['ts']}, "
          f"ventana con errores={float(err[-1]['epoch'])-float(err[0]['epoch']):.1f} s, códigos={sorted(set(r['status'] for r in err))}")
