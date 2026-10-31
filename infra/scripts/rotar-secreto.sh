#!/usr/bin/env bash
# Rotación de la contraseña de la cuenta de ejecución de PostgreSQL (redalimenta_app) sin revelar valores.
# Orden: nuevo valor -> Secrets -> ALTER ROLE -> reinicio gradual de consumidores. Uso: rotar-secreto.sh dev|prod
set -euo pipefail
AMB=${1:?}; R=$(cd "$(dirname "$0")/../.." && pwd); F="$R/secrets/$AMB.env"; K="kubectl --context k3d-ra-$AMB -n redalimenta"
cp "$F" "$F.$(date +%Y%m%d%H%M%S).bak"; chmod 600 "$F".*.bak            # copia de recuperación del valor anterior
NUEVO=$(python3 -c 'import secrets;print(secrets.token_hex(24))')
sed -i "s/^PG_APP=.*/PG_APP=$NUEVO/" "$F"
"$R/infra/scripts/03-secretos.sh" "$AMB" >/dev/null                      # actualiza pg-cuentas, backend-secrets, migraciones-secrets
$K exec -i postgres-0 -- psql -U postgres -d redalimenta -q -v ON_ERROR_STOP=1 -v p="$NUEVO" <<'SQL'
ALTER ROLE redalimenta_app PASSWORD :'p';
SQL
$K rollout restart deploy/backend deploy/outbox >/dev/null
$K rollout status deploy/backend --timeout=180s >/dev/null; $K rollout status deploy/outbox --timeout=180s >/dev/null
echo "rotación completada: huella nueva $(printf %s "$NUEVO" | sha256sum | cut -c1-12)"
