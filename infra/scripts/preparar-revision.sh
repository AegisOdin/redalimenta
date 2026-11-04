#!/usr/bin/env bash
# Deja el equipo listo para la revisión: clústeres arriba, firewall, Jobs sanos, port-forwards y pruebas.
# Uso: infra/scripts/preparar-revision.sh        (detener port-forwards: pkill -f 'port-forward.*monitoring')
set -uo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); cd "$R"
ok() { printf '  \e[32m✓\e[0m %s\n' "$*"; }; mal() { printf '  \e[31m✗\e[0m %s\n' "$*"; }

echo "1) Clústeres"
for c in dev prod; do
  k3d cluster list ra-$c -o json | grep -q '"serversRunning":1' || k3d cluster start ra-$c >/dev/null
  kubectl --context k3d-ra-$c wait --for=condition=Ready nodes --all --timeout=180s >/dev/null && ok "ra-$c: nodos Ready" || mal "ra-$c: nodos no listos"
  kubectl --context k3d-ra-$c -n redalimenta rollout status deploy/backend --timeout=180s >/dev/null && ok "ra-$c: backend disponible" || mal "ra-$c: backend no disponible"
done

echo "2) Firewall de nodos (prod)"
out=$(infra/firewall/asegurar-firewall.sh 2>&1); [ -n "$out" ] && echo "$out" | sed 's/^/     /'
for n in $(docker ps --format '{{.Names}}' | grep -E '^k3d-ra-prod-(server|agent)-[0-9]'); do
  docker exec $n iptables -S RA-FW >/dev/null 2>&1 && ok "$n: cadena RA-FW presente" || mal "$n: sin RA-FW"; done

echo "3) Jobs fallidos (p. ej. CronJobs perdidos durante un reinicio)"
for c in dev prod; do
  K="kubectl --context k3d-ra-$c -n redalimenta"
  F=$($K get jobs -o jsonpath='{range .items[?(@.status.failed)]}{.metadata.name}{"\n"}{end}' | grep -v '^$' || true)
  if [ -n "$F" ]; then
    $K delete job $F >/dev/null; J=respaldo-rev-$(date +%H%M%S)
    $K create job $J --from=cronjob/respaldo >/dev/null
    $K wait --for=condition=complete job/$J --timeout=240s >/dev/null && ok "ra-$c: Jobs fallidos limpiados y respaldo nuevo correcto" || mal "ra-$c: el respaldo manual falló"
  else ok "ra-$c: sin Jobs fallidos"; fi
done

echo "4) Port-forwards de observabilidad (prod, solo localhost)"
pkill -f 'port-forward.*monitoring' 2>/dev/null; sleep 1
pf() { nohup kubectl --context k3d-ra-prod -n monitoring port-forward svc/$1 $2 >/dev/null 2>&1 & }
pf kps-grafana 3000:80; pf kps-prometheus 9090:9090; pf kps-alertmanager 9093:9093; sleep 3
for u in 3000/api/health 9090/-/ready 9093/-/ready; do curl -sf -o /dev/null http://localhost:$u && ok "localhost:${u%%/*}" || mal "localhost:${u%%/*}"; done

echo "5) Resolución de nombres (algunas redes, como las que filtran con FortiGuard, bloquean sslip.io)"
DNS_MAL=""
for par in redalimenta-dev.172-30-0-200.sslip.io:172.30.0.200 redalimenta.172-31-0-200.sslip.io:172.31.0.200; do
  H=${par%%:*}; IP=${par##*:}; real=$(getent ahostsv4 "$H" | awk 'NR==1{print $1}')
  if [ "$real" = "$IP" ]; then ok "$H -> $IP"; else mal "$H resuelve a '${real:-nada}' en vez de $IP"; DNS_MAL=1; fi
done
if [ -n "$DNS_MAL" ]; then
  echo "     La red está bloqueando o cambiando sslip.io. Arréglalo una vez con (pide tu contraseña de sudo):"
  echo "     printf '172.30.0.200 redalimenta-dev.172-30-0-200.sslip.io\n172.31.0.200 redalimenta.172-31-0-200.sslip.io\n' | sudo tee -a /etc/hosts"
fi

echo "6) Pruebas funcionales (con la IP fijada, para no depender del DNS de la red)"
for c in dev prod; do
  H=$([ $c = dev ] && echo redalimenta-dev.172-30-0-200 || echo redalimenta.172-31-0-200).sslip.io
  IP=$([ $c = dev ] && echo 172.30.0.200 || echo 172.31.0.200)
  SEED_PASSWORD=$(grep '^SEED_PASSWORD=' secrets/$c.env | cut -d= -f2-)
  r=$(docker run --rm --network host --add-host "$H:$IP" -u "$(id -u)" -v "$R/secrets/ca-$c.crt:/ca.crt:ro" -e BASE_URL=https://$H -e CA_FILE=/ca.crt \
        -e SEED_PASSWORD="$SEED_PASSWORD" redalimenta-tests:dev 2>&1 | tail -1)
  echo "$r" | grep -q " passed" && ! echo "$r" | grep -qE "failed|error" && ok "$c: $r" || mal "$c: $r"
done

cat <<EOF

Listo. Abre en el navegador:
  App prod   https://redalimenta.172-31-0-200.sslip.io
  App dev    https://redalimenta-dev.172-30-0-200.sslip.io
  Grafana    http://localhost:3000   (usuario admin; contraseña GRAFANA_ADMIN en secrets/prod.env)
  Prometheus http://localhost:9090/alerts
  Alertmanager http://localhost:9093
  Actions    https://github.com/AegisOdin/redalimenta/actions
Usuarios de la app: admin@, coordinador@, social@, voluntario.norte@redalimenta.test (SEED_PASSWORD en secrets/<amb>.env)
EOF
