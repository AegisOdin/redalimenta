#!/usr/bin/env bash
# Restauración verificada en un espacio AISLADO (namespace restauracion), nunca sobre el origen.
# Uso: restaurar.sh <dev|prod> <directorio de respaldo extraído>
# Mide el RTO desde el inicio del script hasta que la aplicación responde con los datos restaurados.
set -euo pipefail
AMB=${1:?}; D=${2:?}; CTX=k3d-ra-$AMB; NS=restauracion; R=$(cd "$(dirname "$0")/.." && pwd)
K="kubectl --context $CTX -n $NS"; T0=$(date +%s); t() { echo "[$(( $(date +%s)-T0 ))s] $*"; }
source "$R/secrets/$AMB.env"
( cd "$D" && sha256sum -c postgres.sha256 mongo.sha256 ) >/dev/null && t "integridad sha256 verificada"
kubectl --context $CTX delete ns $NS --ignore-not-found --wait >/dev/null
kubectl --context $CTX create ns $NS >/dev/null
kubectl --context $CTX label ns $NS pod-security.kubernetes.io/enforce=restricted >/dev/null
TMP=$(python3 -c 'import secrets;print(secrets.token_hex(16))')
$K create secret generic restauracion --from-literal=BACKUP_ENCRYPTION_KEY="$BACKUP_KEY" --from-literal=POSTGRES_PASSWORD="$TMP" \
   --from-literal=MONGO_INITDB_ROOT_USERNAME=root --from-literal=MONGO_INITDB_ROOT_PASSWORD="$TMP" --from-literal=SESSION_SECRET="$SESSION_SECRET" \
   --from-literal=DATABASE_URL="postgresql+psycopg://postgres:$TMP@pg-restaurado:5432/redalimenta" \
   --from-literal=MONGO_URL="mongodb://root:$TMP@mongo-restaurado:27017/redalimenta?authSource=admin" >/dev/null
# Aislamiento de red: solo tráfico interno del namespace (+DNS); sin acceso a las bases de origen
cat <<YAML | $K apply -f - >/dev/null
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: solo-interno}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
  ingress: [{from: [{podSelector: {}}]}]
  egress:
    - to: [{podSelector: {}}]
    - to: [{namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: kube-system}}}]
      ports: [{protocol: UDP, port: 53}, {protocol: TCP, port: 53}]
YAML
IMG=$(kubectl --context $CTX -n redalimenta get deploy backend -o jsonpath='{.spec.template.spec.containers[0].image}')
sed "s#IMAGEN_BACKEND#$IMG#" "$R/respaldos/restauracion.yaml" | $K apply -f - >/dev/null
$K wait pod -l rol=restauracion-bd --for=condition=Ready --timeout=300s >/dev/null; t "motores temporales listos"
$K cp "$D/postgres.dump.enc" pg-restaurado-0:/tmp/postgres.dump.enc -c postgres
$K cp "$D/mongo.archive.enc" mongo-restaurado-0:/tmp/mongo.archive.enc -c mongo
# pg_restore: --no-owner/--no-privileges porque las cuentas de servicio del origen no existen en el espacio aislado
$K exec pg-restaurado-0 -c postgres -- bash -c 'openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_KEY \
  -in /tmp/postgres.dump.enc | pg_restore -U postgres -d redalimenta --no-owner --no-privileges --exit-on-error && rm /tmp/postgres.dump.enc'
t "PostgreSQL restaurado"
$K exec mongo-restaurado-0 -c mongo -- bash -c 'openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_KEY \
  -in /tmp/mongo.archive.enc | mongorestore --quiet --uri="mongodb://root:$MONGO_INITDB_ROOT_PASSWORD@localhost:27017/?authSource=admin" --archive --gzip --drop && rm /tmp/mongo.archive.enc'
t "MongoDB restaurado"
echo "== Conteos esperados (tomados al respaldar)"; echo "postgres: $(cat "$D/postgres-conteos.json")"; echo "mongo:    $(cat "$D/mongo-conteos.json")"
echo "== Conteos restaurados"
PGR=$($K exec pg-restaurado-0 -c postgres -- psql -U postgres -d redalimenta -tAc "select json_object_agg(t, n) from (
  select 'usuarios' t, count(*) n from usuarios union all select 'donantes', count(*) from donantes union all
  select 'productos', count(*) from productos union all select 'lotes', count(*) from lotes union all
  select 'hogares', count(*) from hogares union all select 'despensas', count(*) from despensas union all
  select 'despensa_detalle', count(*) from despensa_detalle union all select 'outbox', count(*) from outbox) x")
MGR=$($K exec mongo-restaurado-0 -c mongo -- bash -c 'mongosh --quiet --norc "mongodb://root:$MONGO_INITDB_ROOT_PASSWORD@localhost:27017/?authSource=admin" --eval "const d=db.getSiblingDB(\"redalimenta\"); print(JSON.stringify({expediente_lote: d.expediente_lote.countDocuments(), bitacora_eventos: d.bitacora_eventos.countDocuments()}))"')
echo "postgres: $PGR"; echo "mongo:    $MGR"
python3 - "$D/postgres-conteos.json" "$PGR" "$D/mongo-conteos.json" "$MGR" <<'PY'
import json,sys
a=json.load(open(sys.argv[1])); b=json.loads(sys.argv[2]); c=json.load(open(sys.argv[3])); d=json.loads(sys.argv[4])
ok = a==b and c==d; print("CONTEOS:", "COINCIDEN" if ok else f"DIFERENTES {a} {b} {c} {d}"); sys.exit(0 if ok else 1)
PY
echo "== Relaciones, restricciones e índices restaurados"
$K exec pg-restaurado-0 -c postgres -- psql -U postgres -d redalimenta -tAc "select contype, count(*) from pg_constraint where connamespace='public'::regnamespace group by 1 order by 1" | sed 's/^/  constraint /'
$K exec pg-restaurado-0 -c postgres -- psql -U postgres -d redalimenta -tAc "select count(*) || ' índices' from pg_indexes where schemaname='public'" | sed 's/^/  /'
$K exec pg-restaurado-0 -c postgres -- psql -U postgres -d redalimenta -tAc "select 'huérfanos detalle->lote: ' || count(*) from despensa_detalle d left join lotes l on l.id=d.lote_id where l.id is null" | sed 's/^/  /'
$K exec pg-restaurado-0 -c postgres -- psql -U postgres -d redalimenta -tAc "select 'registro S-00001: ' || folio || ' ' || estado || ' ' || cantidad_inicial from lotes where folio='S-00001'" | sed 's/^/  /'
$K exec mongo-restaurado-0 -c mongo -- bash -c 'mongosh --quiet --norc "mongodb://root:$MONGO_INITDB_ROOT_PASSWORD@localhost:27017/?authSource=admin" --eval "printjson(db.getSiblingDB(\"redalimenta\").bitacora_eventos.getIndexes().map(i=>i.name)); printjson(db.getSiblingDB(\"redalimenta\").expediente_lote.getIndexes().map(i=>i.name))"' | tr -d '\n' | sed 's/^/  índices mongo: /'; echo
echo "== La aplicación funciona con los datos restaurados"
$K rollout status deploy/backend-restaurado --timeout=180s >/dev/null
$K exec deploy/backend-restaurado -- python -c "
import json,urllib.request,http.cookiejar
cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
r=op.open(urllib.request.Request('http://localhost:8000/api/auth/login',data=json.dumps({'email':'coordinador@redalimenta.test','password':'$SEED_PASSWORD'}).encode(),headers={'content-type':'application/json'}))
print('  login:', r.status)
l=json.load(op.open('http://localhost:8000/api/lotes?size=1')); print('  GET /api/lotes total =', l['total'], 'primero =', l['items'][0]['folio'])
e=json.load(op.open('http://localhost:8000/api/trazabilidad/lotes/S-00001')); print('  expediente S-00001 eventos =', len(e['expediente']['eventos']))
"
t "RTO medido: aplicación respondiendo con datos restaurados"
echo "RTO_SEGUNDOS=$(( $(date +%s)-T0 ))"
echo "Para limpiar: kubectl --context $CTX delete ns $NS"
