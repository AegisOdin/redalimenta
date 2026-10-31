#!/usr/bin/env bash
# E08: conexiones permitidas y denegadas por NetworkPolicy, con DNS y servicios sanos como control.
set -uo pipefail
AMB=${1:-prod}; K="kubectl --context k3d-ra-$AMB -n redalimenta"
SC='"securityContext":{"runAsNonRoot":true,"runAsUser":999,"seccompProfile":{"type":"RuntimeDefault"}},"containers":[{"name":"c","image":"postgres:18.6-bookworm","command":["sleep","600"],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}}}]'
lanzar() { # lanzar <nombre> <labels-json>
  $K delete pod $1 --ignore-not-found --wait >/dev/null 2>&1
  $K run $1 --image=postgres:18.6-bookworm --restart=Never --overrides="{\"metadata\":{\"labels\":$2},\"spec\":{\"automountServiceAccountToken\":false,$SC}}" >/dev/null
  $K wait pod/$1 --for=condition=Ready --timeout=120s >/dev/null; }
tcp() { $K exec $1 -- timeout 4 bash -c "</dev/tcp/$2/$3" >/dev/null 2>&1 && echo "PERMITIDA" || echo "BLOQUEADA"; }
echo "# $(date -u +%FT%TZ) ambiente=$AMB"
echo "== Control: servicios sanos"
$K exec postgres-0 -- pg_isready -h 127.0.0.1 -U postgres
$K get endpointslices -l 'kubernetes.io/service-name in (postgres,mongo)' -o custom-columns=SERVICIO:.metadata.labels.kubernetes\\.io/service-name,ENDPOINTS:.endpoints[*].addresses[0] --no-headers
B=$($K get pod -l app.kubernetes.io/name=backend -o jsonpath='{.items[0].metadata.name}')
echo "== Pod autorizado ($B, rol=api)"
for d in "postgres 5432" "mongo 27017"; do echo "backend -> $d: $($K exec $B -- python -c "
import socket,sys
try: socket.create_connection(('${d% *}',${d#* }),3); print('PERMITIDA')
except Exception as e: print('BLOQUEADA',e)")"; done
echo "backend -> Internet 1.1.1.1:443 (egress no declarado): $($K exec $B -- python -c "
import socket
try: socket.create_connection(('1.1.1.1',443),3); print('PERMITIDA')
except Exception as e: print('BLOQUEADA', type(e).__name__)")"
echo "== Pod NO autorizado (intruso, sin rol)"
lanzar intruso '{"app":"intruso"}'
echo "DNS desde intruso: $($K exec intruso -- getent hosts postgres.redalimenta.svc.cluster.local | awk '{print $1}') (resuelve => DNS permitido)"
echo "intruso -> postgres:5432: $(tcp intruso postgres 5432)"
echo "intruso -> mongo:27017:   $(tcp intruso mongo 27017)"
echo "intruso -> backend:8000 (ingress):  $(tcp intruso backend 8000)"
echo "== Mismo Pod con la etiqueta autorizada rol=respaldos (demuestra que el bloqueo es la política)"
$K label pod intruso rol=respaldos --overwrite >/dev/null; sleep 3
echo "intruso[rol=respaldos] -> postgres:5432: $(tcp intruso postgres 5432)"
echo "intruso[rol=respaldos] -> backend:8000:  $(tcp intruso backend 8000)  (respaldos no tiene salida al backend)"
$K delete pod intruso --wait=false >/dev/null
echo "== Desde otro namespace (default) hacia la BD"
kubectl --context k3d-ra-$AMB -n default run intruso-ns --image=postgres:18.6-bookworm --restart=Never --command -- sleep 120 >/dev/null 2>&1
kubectl --context k3d-ra-$AMB -n default wait pod/intruso-ns --for=condition=Ready --timeout=120s >/dev/null
echo "default/intruso-ns -> postgres.redalimenta:5432: $(kubectl --context k3d-ra-$AMB -n default exec intruso-ns -- timeout 4 bash -c '</dev/tcp/postgres.redalimenta.svc.cluster.local/5432' >/dev/null 2>&1 && echo PERMITIDA || echo BLOQUEADA)"
kubectl --context k3d-ra-$AMB -n default delete pod intruso-ns --wait=false >/dev/null
echo "== Políticas vigentes"; $K get networkpolicy
