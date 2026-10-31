#!/usr/bin/env bash
# Prueba del firewall de nodos de prod desde un origen NO autorizado (contenedor en la red de nodos, IP .50)
# y desde el host. Las líneas BLOQUEADO deben fallar por timeout; PERMITIDO debe responder.
set -uo pipefail
CA=${CA:-secrets/ca-prod.crt}; S=172.31.0.3; A=172.31.0.4
NP=$(kubectl --context k3d-ra-prod -n traefik get svc traefik -o jsonpath='{.spec.ports[?(@.name=="websecure")].nodePort}')
p() { if eval "$2" >/dev/null 2>&1; then echo "$1: RESPONDE"; else echo "$1: SIN RESPUESTA (bloqueado/timeout)"; fi; }
echo "== Origen no autorizado: contenedor 172.31.0.50 en ra-prod-net"
docker run --rm --network ra-prod-net --ip 172.31.0.50 curlimages/curl:8.17.0 sh -c "
  for t in 'API server directo $S:6443|https://$S:6443/version' 'kubelet $A:10250|https://$A:10250/healthz' \
           'NodePort Traefik $A:$NP|https://$A:$NP/' 'node-exporter $A:9100|http://$A:9100/metrics'; do
    n=\${t%%|*}; u=\${t#*|}; if curl -sk -m 4 -o /dev/null \$u; then echo \"\$n: RESPONDE\"; else echo \"\$n: SIN RESPUESTA (bloqueado)\"; fi; done"
echo "== Host administrador (172.31.0.1)"
p "API directo al nodo $S:6443 (no permitido)" "curl -sk -m 4 https://$S:6443/version"
p "NodePort $A:$NP (no permitido)" "curl -sk -m 4 https://$A:$NP/"
p "API vía red de administración 127.0.0.1:6552 (permitido)" "kubectl --context k3d-ra-prod get --raw /readyz"
p "Entrada web HTTPS 172.31.0.200:443 (permitido)" "curl -s -m 4 --cacert $CA https://redalimenta.172-31-0-200.sslip.io/api/version"
echo "== Contadores de la regla 'descartar resto' por nodo"
for n in k3d-ra-prod-server-0 k3d-ra-prod-agent-0 k3d-ra-prod-agent-1; do
  echo "$n: $(docker exec $n iptables -L RA-FW -v -n | awk '/descartar resto/{print $1" paquetes descartados"}')"; done
