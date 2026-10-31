#!/usr/bin/env bash
# E07: varias réplicas atienden solicitudes. Activa temporalmente el identificador de réplica y lo retira al final.
set -uo pipefail
K="kubectl --context k3d-ra-prod -n redalimenta"; CA=${CA:-secrets/ca-prod.crt}; H=https://redalimenta.172-31-0-200.sslip.io
esperar() { $K rollout status deploy/backend --timeout=180s >/dev/null
  while [ "$($K get pods -l app.kubernetes.io/name=backend --no-headers | wc -l)" != "$($K get deploy backend -o jsonpath='{.spec.replicas}')" ]; do sleep 2; done; }
echo "# E07 Balanceo $(date -u +%FT%TZ) — DIAG_REPLICA activado solo durante la prueba"
$K set env deploy/backend DIAG_REPLICA=true >/dev/null; esperar
echo "== Réplicas backend y nodo"; $K get pods -l app.kubernetes.io/name=backend -o custom-columns=POD:.metadata.name,NODO:.spec.nodeName,IP:.status.podIP --no-headers
echo "== 100 solicitudes HTTPS, conexión nueva cada una (MetalLB -> Traefik -> réplicas)"
for i in $(seq 100); do curl -s --cacert $CA $H/api/diag/replica | python3 -c 'import json,sys
try: print(json.load(sys.stdin)["replica"])
except Exception: print("respuesta-no-json")'; done | sort | uniq -c
$K set env deploy/backend DIAG_REPLICA- >/dev/null; esperar
echo "== Identificador retirado: HTTP $(curl -s -o /dev/null -w '%{http_code}' --cacert $CA $H/api/diag/replica) (404 esperado)"
echo "== Distribución entre workers (topologySpreadConstraints maxSkew=1)"
$K get pods -l 'app.kubernetes.io/name in (backend,frontend)' -o custom-columns=POD:.metadata.name,NODO:.spec.nodeName --no-headers | sort -k2
