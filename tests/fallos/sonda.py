#!/usr/bin/env python3
"""Sonda de tráfico continuo (cada 0.25 s): GET /api/lotes (consulta BD) y registra estado y latencia en CSV.
Uso: sonda.py <url_base> <ca> <password> <salida.csv>   (se detiene con SIGTERM)"""
import csv, json, signal, ssl, sys, time, urllib.request, http.cookiejar
base, ca, pwd, out = sys.argv[1:5]
ctx = ssl.create_default_context(cafile=ca)
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), urllib.request.HTTPCookieProcessor(cj))
def login():
    op.open(urllib.request.Request(base + "/api/auth/login", data=json.dumps({"email": "coordinador@redalimenta.test", "password": pwd}).encode(),
                                   headers={"content-type": "application/json"}), timeout=5)
login()
corriendo = True
signal.signal(signal.SIGTERM, lambda *a: globals().update(corriendo=False))
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["ts", "epoch", "status", "ms"])
    while corriendo:
        t0 = time.time()
        try:
            r = op.open(base + "/api/lotes?size=5", timeout=5); st = r.status
        except urllib.error.HTTPError as e:
            st = e.code
        except Exception:
            st = 0
        w.writerow([time.strftime("%H:%M:%S"), round(t0, 2), st, round((time.time() - t0) * 1000)]); f.flush()
        time.sleep(0.25)
