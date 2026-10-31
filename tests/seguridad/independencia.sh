#!/usr/bin/env bash
# E02: URLs HTTPS distintas, CA/certificados distintos y datos independientes entre ambientes.
set -uo pipefail
R=$(cd "$(dirname "$0")/../.." && pwd); DEV=https://redalimenta-dev.172-30-0-200.sslip.io; PROD=https://redalimenta.172-31-0-200.sslip.io
CAD=${CAD:-$R/secrets/ca-dev.crt}; CAP=${CAP:-$R/secrets/ca-prod.crt}
echo "# $(date -u +%FT%TZ)"
for a in "dev $DEV $CAD" "prod $PROD $CAP"; do set -- $a
  echo "== $1: $2 -> $(curl -s --cacert $3 $2/api/version)"
  echo | openssl s_client -connect ${2#https://}:443 -servername ${2#https://} -CAfile $3 2>/dev/null | grep -E "^subject=|^issuer=|Verify return code" | sed 's/^/   /'
done
echo "== El certificado de prod NO es válido con la CA de dev: $(curl -s -o /dev/null -w '%{http_code}' --cacert $CAD $PROD/api/version 2>&1 || true) (000 = verificación TLS fallida)"
echo "== Datos independientes: se crea un hogar solo en dev"
source "$R/secrets/dev.env"; CLAVE="IND-$(date +%H%M%S)"
python3 - "$DEV" "$CAD" "$SEED_PASSWORD" "$CLAVE" <<'PY'
import json, ssl, sys, urllib.request, http.cookiejar
base, ca, pwd, clave = sys.argv[1:5]
op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca)), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
r = json.load(op.open(urllib.request.Request(base + "/api/auth/login", data=json.dumps({"email": "social@redalimenta.test", "password": pwd}).encode(), headers={"content-type": "application/json"})))
op.open(urllib.request.Request(base + "/api/hogares", data=json.dumps({"clave": clave, "responsable": "Solo en desarrollo", "integrantes": 2, "colonia": "Col. Dev", "ruta": "Norte"}).encode(), headers={"content-type": "application/json", "x-csrf-token": r["csrf"]}))
print(f"   creado {clave} en dev")
PY
for a in "dev k3d-ra-dev" "prod k3d-ra-prod"; do set -- $a
  echo "   $1: hogares con clave $CLAVE = $(kubectl --context $2 -n redalimenta exec postgres-0 -- psql -U postgres -d redalimenta -tAc "select count(*) from hogares where clave='$CLAVE'") · total hogares = $(kubectl --context $2 -n redalimenta exec postgres-0 -- psql -U postgres -d redalimenta -tAc 'select count(*) from hogares')"; done
echo "== Credenciales distintas (huella SHA-256 truncada del secreto de sesión, sin revelarlo)"
for a in dev prod; do echo "   $a: $(kubectl --context k3d-ra-$a -n redalimenta get secret backend-secrets -o jsonpath='{.data.SESSION_SECRET}' | base64 -d | sha256sum | cut -c1-12)"; done
echo "== Volúmenes distintos"
for a in dev prod; do echo "   $a:"; kubectl --context k3d-ra-$a -n redalimenta get pvc -o custom-columns=PVC:.metadata.name,VOLUMEN:.spec.volumeName,TAMAÑO:.spec.resources.requests.storage --no-headers | sed 's/^/     /'; done
