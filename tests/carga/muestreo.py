#!/usr/bin/env python3
"""Serie temporal cada 10 s: réplicas deseadas/actuales/Ready del HPA, CPU, RPS, p95, errores y conexiones a BD.
Fuente: API de Kubernetes y Prometheus (port-forward localhost:9090). Uso: muestreo.py <salida.csv> <etiqueta>"""
import csv, json, subprocess, sys, time, urllib.parse, urllib.request
out, etiqueta = sys.argv[1], sys.argv[2]
PROM = "http://localhost:9090/api/v1/query?query="
Q = {
    "rps": 'sum(rate(redalimenta_http_requests_total{route=~"/api/(lotes|hogares)"}[1m]))',
    "p95_s": 'histogram_quantile(0.95, sum by (le) (rate(redalimenta_http_request_duration_seconds_bucket{route=~"/api/(lotes|hogares)"}[1m])))',
    "errores_ratio": 'sum(rate(redalimenta_http_requests_total{status=~"5.."}[1m])) / clamp_min(sum(rate(redalimenta_http_requests_total[1m])),0.001)',
    "cpu_backend_cores": 'sum(rate(container_cpu_usage_seconds_total{namespace="redalimenta",pod=~"backend-.*",container="backend"}[1m]))',
    "cpu_postgres_cores": 'sum(rate(container_cpu_usage_seconds_total{namespace="redalimenta",pod="postgres-0",container="postgres"}[1m]))',
    "mem_backend_mib": 'sum(container_memory_working_set_bytes{namespace="redalimenta",pod=~"backend-.*",container="backend"})/1048576',
    "pg_conexiones": 'sum(pg_stat_activity_count{datname="redalimenta"})',
}
def prom(q):
    try:
        r = json.load(urllib.request.urlopen(PROM + urllib.parse.quote(q), timeout=5))["data"]["result"]
        return round(float(r[0]["value"][1]), 4) if r else 0
    except Exception:
        return ""
def kj(*a):
    try:
        return json.loads(subprocess.run(["kubectl", "--context", "k3d-ra-prod", "-n", "redalimenta", *a, "-o", "json"],
                                         capture_output=True, text=True, timeout=10).stdout)
    except Exception:
        return {}
with open(out, "a", newline="") as f:
    w = csv.writer(f)
    if f.tell() == 0:
        w.writerow(["ts", "etiqueta", "hpa_deseadas", "hpa_actuales", "ready", "pending", "cpu_hpa_pct", *Q.keys()])
    while True:
        hpa = kj("get", "hpa", "backend"); dep = kj("get", "deploy", "backend")
        pods = kj("get", "pods", "-l", "app.kubernetes.io/name=backend").get("items", [])
        st = hpa.get("status", {})
        cpu = next((m["resource"]["current"].get("averageUtilization") for m in st.get("currentMetrics") or [] if m.get("type") == "Resource"), "")
        w.writerow([time.strftime("%Y-%m-%dT%H:%M:%S"), etiqueta, st.get("desiredReplicas", dep.get("spec", {}).get("replicas", "")),
                    st.get("currentReplicas", dep.get("status", {}).get("replicas", "")), dep.get("status", {}).get("readyReplicas", ""),
                    sum(1 for p in pods if p["status"].get("phase") == "Pending"), cpu, *[prom(q) for q in Q.values()]])
        f.flush(); time.sleep(10)
