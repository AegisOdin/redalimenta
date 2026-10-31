#!/usr/bin/env bash
# E06 (repetición): misma corrida con HPA tras corregir la distribución (nodeTaintsPolicy: Honor).
# Generador: equipo administrador (contenedor grafana/k6:1.8.2, fuera del clúster) -> HTTPS por MetalLB/Traefik.
set -uo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); O="$R/docs/evidencias/carga"; mkdir -p "$O"; source "$R/secrets/prod.env"
K="kubectl --context k3d-ra-prod -n redalimenta"; CA=${CA:-$R/secrets/ca-prod.crt}
BASE=https://redalimenta.172-31-0-200.sslip.io; IMG=grafana/k6:1.8.2
BASELINE='[{"duration":"5m","target":2}]'
RAMPA='[{"duration":"2m","target":10},{"duration":"3m","target":30},{"duration":"3m","target":60},{"duration":"3m","target":60},{"duration":"1m","target":0}]'
k6() { docker run --rm --network host -u "$(id -u)" -v "$R/tests/carga:/s:ro" -v "$O:/o" -v "$CA:/ca.crt:ro" -e SSL_CERT_FILE=/ca.crt \
       -e BASE_URL=$BASE -e SEED_PASSWORD="$SEED_PASSWORD" -e STAGES="$2" $IMG run --quiet --summary-export /o/k6-$1.json /s/escenario.js > "$O/k6-$1.txt" 2>&1; }
corrida() { # corrida <etiqueta>
  python3 "$R/tests/carga/muestreo.py" "$O/serie-$1.csv" "$1" & S=$!
  echo "[$(date +%T)] $1: línea base 5 min"; k6 "$1-base" "$BASELINE"
  echo "[$(date +%T)] $1: rampa 12 min"; k6 "$1-rampa" "$RAMPA"
  echo "[$(date +%T)] $1: enfriamiento (ventana de estabilización 180 s + reducción 1 pod/min)"
  for i in $(seq 60); do [ "$($K get deploy backend -o jsonpath='{.status.readyReplicas}')" = 2 ] && [ $i -gt 18 ] && break; sleep 10; done
  sleep 30; kill $S; echo "[$(date +%T)] $1: fin"; }
echo "k6 $(docker run --rm $IMG version | head -1)" > "$O/herramienta.txt"
ETQ=${1:-con-hpa-v2}
$K get hpa backend -o yaml > "$O/hpa-config-$ETQ.yaml"
kubectl --context k3d-ra-prod -n redalimenta get deploy backend -o jsonpath='{.spec.template.spec.topologySpreadConstraints}' > "$O/topologia-$ETQ.json"
corrida $ETQ
$K describe hpa backend > "$O/describe-hpa-$ETQ.txt"
$K get events --sort-by=.lastTimestamp | grep -i -E "SuccessfulRescale|FailedScheduling" > "$O/eventos-hpa-$ETQ.txt" || true
