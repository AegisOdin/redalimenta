#!/usr/bin/env bash
# Paso 4: crea los Secrets de un ambiente sin escribirlos en Git ni mostrarlos en pantalla.
# Los valores se generan al azar la primera vez y se guardan en secrets/<amb>.env (chmod 600, ignorado por Git)
# para recuperación. Rotación: ver D06 (rotar.sh). Uso: 03-secretos.sh dev|prod
set -euo pipefail
AMB=${1:?dev|prod}; CTX=k3d-ra-$AMB; NS=redalimenta
R=$(cd "$(dirname "$0")/../.." && pwd); F="$R/secrets/$AMB.env"
mkdir -p "$R/secrets"; chmod 700 "$R/secrets"
gen() { python3 -c 'import secrets;print(secrets.token_hex(24))'; }
umask 077; touch "$F"
for v in PG_SUPER PG_MIG PG_APP PG_BACKUP PG_EXPORTER MONGO_ROOT MONGO_APP MONGO_MIG MONGO_BACKUP MONGO_EXPORTER \
         SESSION_SECRET BACKUP_KEY; do   # solo genera los que falten (idempotente)
  grep -q "^$v=" "$F" || echo "$v=$(gen)" >> "$F"
done
grep -q "^SEED_PASSWORD=" "$F" || echo "SEED_PASSWORD=Demo-$AMB-$(python3 -c 'import secrets;print(secrets.token_urlsafe(9))')" >> "$F"
set -a; source "$F"; set +a
if [ "$AMB" = prod ]; then
  CA=/etc/redalimenta-ca/ca.crt
  PGQ="?sslmode=verify-full&sslrootcert=$CA"; MQ="&tls=true&tlsCAFile=$CA"
else PGQ=""; MQ=""; fi
K="kubectl --context $CTX -n $NS"
kubectl --context $CTX get ns $NS >/dev/null 2>&1 || kubectl --context $CTX apply -f "$R/k8s/base/namespace.yaml"
mk() { # mk <nombre> <k=v>...   (aplica sin imprimir valores)
  local n=$1; shift; local args=(); for kv in "$@"; do args+=(--from-literal="$kv"); done
  $K create secret generic "$n" "${args[@]}" --dry-run=client -o yaml | $K apply -f - >/dev/null; echo "secret/$n aplicado"; }
mk pg-superuser POSTGRES_PASSWORD=$PG_SUPER
mk pg-cuentas MIGRATOR_PASSWORD=$PG_MIG APP_PASSWORD=$PG_APP BACKUP_PASSWORD=$PG_BACKUP EXPORTER_PASSWORD=$PG_EXPORTER
mk mongo-root MONGO_INITDB_ROOT_USERNAME=root MONGO_INITDB_ROOT_PASSWORD=$MONGO_ROOT
mk mongo-cuentas APP_PASSWORD=$MONGO_APP MIGRATOR_PASSWORD=$MONGO_MIG BACKUP_PASSWORD=$MONGO_BACKUP EXPORTER_PASSWORD=$MONGO_EXPORTER
mk backend-secrets SESSION_SECRET=$SESSION_SECRET \
   "DATABASE_URL=postgresql+psycopg://redalimenta_app:$PG_APP@postgres:5432/redalimenta$PGQ" \
   "MONGO_URL=mongodb://redalimenta_app:$MONGO_APP@mongo:27017/redalimenta?authSource=redalimenta$MQ"
mk migraciones-secrets SESSION_SECRET=$SESSION_SECRET SEED_PASSWORD=$SEED_PASSWORD \
   "MIGRATION_DATABASE_URL=postgresql+psycopg://redalimenta_migrator:$PG_MIG@postgres:5432/redalimenta$PGQ" \
   "SEED_DATABASE_URL=postgresql+psycopg://redalimenta_app:$PG_APP@postgres:5432/redalimenta$PGQ" \
   "MONGO_URL=mongodb://redalimenta_migrator:$MONGO_MIG@mongo:27017/redalimenta?authSource=redalimenta$MQ"
mk respaldo-secrets PGPASSWORD=$PG_BACKUP BACKUP_ENCRYPTION_KEY=$BACKUP_KEY \
   "MONGO_BACKUP_URI=mongodb://redalimenta_backup:$MONGO_BACKUP@mongo:27017/?authSource=admin$MQ"
mk exporter-postgres "DATA_SOURCE_NAME=postgresql://redalimenta_exporter:$PG_EXPORTER@postgres:5432/redalimenta${PGQ:-?sslmode=disable}"
mk exporter-mongo "MONGODB_URI=mongodb://redalimenta_exporter:$MONGO_EXPORTER@mongo:27017/admin?authSource=admin$MQ"
# CA pública del ambiente (solo certificado, sin llave) para que los clientes verifiquen a los motores
kubectl --context $CTX -n cert-manager get secret redalimenta-lab-ca -o jsonpath='{.data.ca\.crt}' | base64 -d > /tmp/ca-$AMB.crt
$K create configmap ca-laboratorio --from-file=ca.crt=/tmp/ca-$AMB.crt --dry-run=client -o yaml | $K apply -f - >/dev/null
cp /tmp/ca-$AMB.crt "$R/secrets/ca-$AMB.crt"; rm -f /tmp/ca-$AMB.crt; echo "configmap/ca-laboratorio aplicado"
