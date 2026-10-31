#!/usr/bin/env bash
# E05, E10, E11, E12 en producción. Cada prueba registra línea de tiempo, sonda de tráfico y verificación.
# Uso: fallos.sh <prueba>   pruebas: pod-backend | drain | postgres-caido | mongo-caido | pods-datos | actualizacion
set -uo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); O="$R/docs/evidencias/fallos"; mkdir -p "$O"; source "$R/secrets/prod.env"
K="kubectl --context k3d-ra-prod -n redalimenta"; CA=${CA:-$R/secrets/ca-prod.crt}; BASE=https://redalimenta.172-31-0-200.sslip.io
T0=$(date +%s); t() { echo "[$(date +%T) +$(( $(date +%s)-T0 ))s] $*"; }
sonda_ini() { python3 "$R/tests/fallos/sonda.py" $BASE "$CA" "$SEED_PASSWORD" "$O/sonda-$1.csv" & SONDA=$!; sleep 3; }
sonda_fin() { kill $SONDA; sleep 1; echo "== Impacto en solicitudes (sonda cada 0.25 s)"; python3 "$R/tests/fallos/resumen.py" "$O/sonda-$1.csv"; }
reinicios() { $K get pods -l app.kubernetes.io/name=backend -o jsonpath='{range .items[*]}{.metadata.name}={.status.containerStatuses[0].restartCount} {end}'; }
pg() { $K exec postgres-0 -- psql -U postgres -d redalimenta -tAc "$1"; }
mongo_q() { $K exec mongo-0 -- mongosh --quiet --norc --tls --tlsCAFile /tls/ca.crt --host localhost -u redalimenta_app -p "$MONGO_APP" --authenticationDatabase redalimenta redalimenta --eval "$1"; }
case "$1" in
pod-backend)
  sonda_ini pod-backend; P=$($K get pods -l app.kubernetes.io/name=backend -o jsonpath='{.items[0].metadata.name}')
  t "Réplicas antes:"; $K get pods -l app.kubernetes.io/name=backend -o wide --no-headers | awk '{print "   ",$1,$2,$7}'
  t "Elimino $P"; $K delete pod $P --wait=false
  until [ "$($K get deploy backend -o jsonpath='{.status.readyReplicas}')" = "$($K get deploy backend -o jsonpath='{.spec.replicas}')" ] && ! $K get pod $P >/dev/null 2>&1; do sleep 1; done
  t "Réplica recreada y Ready:"; $K get pods -l app.kubernetes.io/name=backend -o wide --no-headers | awk '{print "   ",$1,$2,$5,$7}'
  sleep 10; sonda_fin pod-backend ;;
drain)
  N=$($K get pod mongo-0 -o jsonpath='{.spec.nodeName}')
  sonda_ini drain; t "Antes del mantenimiento ($N aloja mongo-0 con volumen local):"; $K get pods -o wide --no-headers | awk '{print "   ",$1,$3,$7}'
  $K get pdb
  t "kubectl drain $N --ignore-daemonsets --delete-emptydir-data (sin --force; respeta PDB)"
  kubectl --context k3d-ra-prod drain $N --ignore-daemonsets --delete-emptydir-data --timeout=180s 2>&1 | grep -v "^WARNING\|Warning" | sed 's/^/    /'
  t "Durante el mantenimiento:"; $K get pods -o wide --no-headers | awk '{print "   ",$1,$3,$7}'
  kubectl --context k3d-ra-prod get nodes --no-headers | sed 's/^/    /'
  t "mongo-0 queda Pending: su PV local-path tiene afinidad a $N (limitación documentada). La API sigue atendiendo:"
  curl -s -o /dev/null -w "    GET /api/version durante el drain: HTTP %{http_code}\n" --cacert "$CA" $BASE/api/version
  sleep 45; t "Outbox pendiente durante la ventana: $(pg 'select count(*) from outbox where publicado_en is null')"
  t "kubectl uncordon $N"; kubectl --context k3d-ra-prod uncordon $N
  $K rollout status statefulset/mongo --timeout=300s >/dev/null; t "mongo-0 de vuelta en $N"
  for i in $(seq 30); do [ "$(pg 'select count(*) from outbox where publicado_en is null')" = 0 ] && break; sleep 2; done
  t "Outbox pendiente tras la recuperación: $(pg 'select count(*) from outbox where publicado_en is null')"
  t "Rebalanceo tras el mantenimiento (el scheduler no mueve Pods ya en ejecución): rollout restart"
  $K rollout restart deploy/backend deploy/frontend >/dev/null; $K rollout status deploy/backend --timeout=180s >/dev/null; $K rollout status deploy/frontend --timeout=180s >/dev/null
  while [ "$($K get pods -l app.kubernetes.io/name=backend --no-headers | wc -l)" != 2 ]; do sleep 1; done
  t "Distribución final:"; $K get pods -o wide --no-headers | awk '{print "   ",$1,$3,$7}'
  sonda_fin drain ;;
postgres-caido)
  sonda_ini postgres; t "Reinicios backend antes: $(reinicios)"
  t "Simulo indisponibilidad: scale statefulset/postgres --replicas=0"; $K scale statefulset postgres --replicas=0
  sleep 15; t "Respuesta de la API con PostgreSQL caído:"
  curl -s --cacert "$CA" -X POST $BASE/api/auth/login -H 'content-type: application/json' -d '{"email":"admin@redalimenta.test","password":"x"}' | sed 's/^/    /'; echo
  t "Endpoints listos del Service backend: $($K get endpointslices -l kubernetes.io/service-name=backend -o jsonpath='{range .items[*].endpoints[*]}{.conditions.ready} {end}')"
  echo "    (readiness retira las réplicas; liveness NO las reinicia)"
  t "Lanzo un respaldo mientras la BD está caída (debe fallar y disparar RespaldoFallido)"
  $K delete job respaldo-durante-caida --ignore-not-found >/dev/null; $K create job respaldo-durante-caida --from=cronjob/respaldo
  sleep 75; t "Reinicios backend durante la caída: $(reinicios)"
  t "Restablezco PostgreSQL"; $K scale statefulset postgres --replicas=1; $K rollout status statefulset/postgres --timeout=300s >/dev/null
  until [ "$($K get deploy backend -o jsonpath='{.status.readyReplicas}')" -ge 2 ] 2>/dev/null; do sleep 1; done
  t "Backend Ready otra vez. Reinicios después: $(reinicios)"
  t "Estado del Job de respaldo: $($K get job respaldo-durante-caida -o jsonpath='{.status.failed}') fallido(s)"
  sleep 10; sonda_fin postgres ;;
mongo-caido)
  B0=$(mongo_q 'db.bitacora_eventos.countDocuments()'); t "bitacora_eventos antes: $B0"
  sonda_ini mongo; t "Simulo indisponibilidad: scale statefulset/mongo --replicas=0"; $K scale statefulset mongo --replicas=0; sleep 10
  t "Genero 80 operaciones de negocio (lotes) mientras MongoDB está caído"
  python3 - "$BASE" "$CA" "$SEED_PASSWORD" <<'PY'
import json, ssl, sys, urllib.request, http.cookiejar, datetime
base, ca, pwd = sys.argv[1:4]
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca)), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
r = json.load(op.open(urllib.request.Request(base + "/api/auth/login", data=json.dumps({"email": "coordinador@redalimenta.test", "password": pwd}).encode(), headers={"content-type": "application/json"})))
csrf = r["csrf"]; ok = 0
for i in range(80):
    body = json.dumps({"producto_id": 7, "donante_id": 1, "cantidad_inicial": 10, "fecha_caducidad": str(datetime.date.today() + datetime.timedelta(days=60))}).encode()
    try:
        op.open(urllib.request.Request(base + "/api/lotes", data=body, headers={"content-type": "application/json", "x-csrf-token": csrf})); ok += 1
    except Exception as e:
        print("error", e)
print(f"    lotes creados con MongoDB caído: {ok}/80 (la operación del almacén no se detiene)")
try:
    op.open(base + "/api/trazabilidad/lotes/S-00001")
except urllib.error.HTTPError as e:
    print(f"    rastreo de lote: HTTP {e.code} {json.load(e)['detail'][:90]}")
PY
  t "Eventos en outbox pendientes: $(pg 'select count(*) from outbox where publicado_en is null') · intentos acumulados: $(pg 'select coalesce(sum(intentos),0) from outbox where publicado_en is null')"
  t "Espero 6 min con MongoDB caído para observar alertas BaseDeDatosCaida y OutboxAtrasado"; sleep 360
  curl -s 'http://localhost:9090/api/v1/alerts' | python3 -c 'import json,sys;[print("    ALERTA",a["labels"]["alertname"],a["state"],a.get("activeAt","")) for a in json.load(sys.stdin)["data"]["alerts"] if a["labels"]["alertname"] not in ("Watchdog","InfoInhibitor")]'
  t "Restablezco MongoDB"; $K scale statefulset mongo --replicas=1; $K rollout status statefulset/mongo --timeout=300s >/dev/null
  for i in $(seq 60); do [ "$(pg 'select count(*) from outbox where publicado_en is null')" = 0 ] && break; sleep 2; done
  t "Outbox pendiente tras reconexión: $(pg 'select count(*) from outbox where publicado_en is null')"
  B1=$(mongo_q 'db.bitacora_eventos.countDocuments()'); P=$(pg 'select count(*) from outbox where publicado_en is not null')
  D=$(mongo_q 'db.bitacora_eventos.aggregate([{$group:{_id:"$event_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}]).toArray().length')
  t "Reconciliación: bitacora_eventos $B0 -> $B1 · eventos publicados en PostgreSQL $P · event_id duplicados: $D"
  t "Reintento forzado (idempotencia): reproyecto los últimos 15 min y verifico que no se duplica nada"
  $K exec deploy/backend -- python -m app.tasks reproyectar "$(date -u -d '-15 min' +%Y-%m-%dT%H:%M:%S+00:00)"
  for i in $(seq 60); do [ "$(pg 'select count(*) from outbox where publicado_en is null')" = 0 ] && break; sleep 2; done
  t "Tras reproyección: bitacora_eventos=$(mongo_q 'db.bitacora_eventos.countDocuments()') duplicados=$(mongo_q 'db.bitacora_eventos.aggregate([{$group:{_id:"$event_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}]).toArray().length') eventos repetidos en expedientes=$(mongo_q 'db.expediente_lote.aggregate([{$unwind:"$eventos"},{$group:{_id:"$eventos.event_id",n:{$sum:1}}},{$match:{n:{$gt:1}}}]).toArray().length')"
  sonda_fin mongo ;;
pods-datos)
  A=$(pg "select count(*) from lotes")/$(pg "select count(*) from despensas"); M=$(mongo_q 'db.expediente_lote.countDocuments()')
  t "Antes: lotes/despensas=$A expedientes=$M · nodo postgres=$($K get pod postgres-0 -o jsonpath='{.spec.nodeName}') mongo=$($K get pod mongo-0 -o jsonpath='{.spec.nodeName}')"
  t "Elimino postgres-0 y mongo-0"; $K delete pod postgres-0 mongo-0
  $K rollout status statefulset/postgres --timeout=300s >/dev/null; $K rollout status statefulset/mongo --timeout=300s >/dev/null
  t "Recreados. Después: lotes/despensas=$(pg "select count(*) from lotes")/$(pg "select count(*) from despensas") expedientes=$(mongo_q 'db.expediente_lote.countDocuments()') · mismo PVC: $($K get pvc -o custom-columns=PVC:.metadata.name,VOLUMEN:.spec.volumeName --no-headers | tr '\n' ' ')" ;;
actualizacion)
  sonda_ini actualizacion
  t "Versión en producción: $(curl -s --cacert "$CA" $BASE/api/version)"; $K rollout history deploy/backend | tail -3
  t "Promuevo el artefacto aprobado en dev (1.1.1) — mismo digest, solo cambia la configuración del overlay"
  "$R/infra/scripts/promover.sh" prod "$(ls -t $R/docs/evidencias/ci/build-1.1.1-*.txt | head -1)"
  "$R/infra/scripts/04-desplegar.sh" prod > "$O/despliegue-1.1.1.log" 2>&1
  while [ "$($K get pods -l app.kubernetes.io/name=backend --no-headers | wc -l)" != 2 ]; do sleep 1; done
  t "Versión tras rolling update: $(curl -s --cacert "$CA" $BASE/api/version) · migración: $(pg 'select version_num from alembic_version')"
  $K get pods -l app.kubernetes.io/name=backend -o custom-columns=POD:.metadata.name,IMAGEN:.spec.containers[0].image --no-headers | sed 's/^/    /'
  t "Rollback: kubectl rollout undo deploy/backend y deploy/frontend (el esquema 0002 es compatible con 1.0.0; no se revierte)"
  $K rollout undo deploy/backend; $K rollout undo deploy/frontend; $K rollout status deploy/backend --timeout=300s >/dev/null; $K rollout status deploy/frontend --timeout=300s >/dev/null
  while [ "$($K get pods -l app.kubernetes.io/name=backend --no-headers | wc -l)" != 2 ]; do sleep 1; done   # Pods viejos drenados (preStop)
  t "Versión tras rollback: $(curl -s --cacert "$CA" $BASE/api/version) · migración sigue en $(pg 'select version_num from alembic_version')"
  $K rollout history deploy/backend | tail -4 | sed 's/^/    /'
  docker run --rm --network host -v "$CA:/ca.crt:ro" -e BASE_URL=$BASE -e CA_FILE=/ca.crt -e SEED_PASSWORD="$SEED_PASSWORD" redalimenta-tests:dev 2>&1 | tail -1 | sed 's/^/    pruebas funcionales tras rollback: /'
  sonda_fin actualizacion ;;
esac
