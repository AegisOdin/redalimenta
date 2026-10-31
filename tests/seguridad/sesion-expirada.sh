#!/usr/bin/env bash
# Sesión expirada: se firma DENTRO del Pod (el secreto nunca sale del clúster) un token con exp en el pasado
# y se usa contra la API publicada por HTTPS. Se espera 401 "Sesión expirada"; con el mismo flujo y exp futuro, 200.
set -uo pipefail
AMB=${1:-prod}; R=$(cd "$(dirname "$0")/../.." && pwd); CA=${CA:-$R/secrets/ca-$AMB.crt}
H=$([ $AMB = dev ] && echo https://redalimenta-dev.172-30-0-200.sslip.io || echo https://redalimenta.172-31-0-200.sslip.io)
K="kubectl --context k3d-ra-$AMB -n redalimenta"
tok() { $K exec deploy/backend -- python -c "
import jwt,os,datetime as d
print(jwt.encode({'sub':'2','rol':'coordinador','csrf':'x','exp':d.datetime.now(d.timezone.utc)+d.timedelta(minutes=$1)},os.environ['SESSION_SECRET'],algorithm='HS256'))"; }
echo "# Sesión expirada ($AMB) $(date -u +%FT%TZ)"
E=$(tok -1); V=$(tok 5)
echo "token vencido hace 1 min  -> $(curl -s -w ' HTTP %{http_code}' --cacert $CA -b "ra_session=$E" $H/api/auth/me)"
echo "token vigente (control)   -> HTTP $(curl -s -o /dev/null -w '%{http_code}' --cacert $CA -b "ra_session=$V" $H/api/auth/me)"
echo "duración configurada de la sesión: $($K get cm -o jsonpath='{.items[?(@.data.SESSION_MINUTES)].data.SESSION_MINUTES}') min (cookie Max-Age y claim exp)"
echo "cabecera Set-Cookie del login (atributos):"
source "$R/secrets/$AMB.env"; curl -s -D - -o /dev/null --cacert $CA -H 'content-type: application/json' -d "{\"email\":\"coordinador@redalimenta.test\",\"password\":\"$SEED_PASSWORD\"}" $H/api/auth/login | grep -i '^set-cookie' | sed -E 's/(ra_session|ra_csrf)=[^;]+/\1=<oculto>/'
