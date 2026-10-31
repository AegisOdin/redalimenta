#!/usr/bin/env bash
# CI equivalente ejecutable localmente: validación de manifiestos, construcción + Trivy + push, despliegue en dev
# y pruebas funcionales. Uso: ci-local.sh <version>
set -euo pipefail
V=${1:?version}; R=$(cd "$(dirname "$0")/../.." && pwd); cd "$R"
for a in dev prod; do kubectl kustomize k8s/overlays/$a > /tmp/ci-$a.yaml; done
docker run --rm -v /tmp:/m ghcr.io/yannh/kubeconform:v0.7.0 -strict -summary -ignore-missing-schemas -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' /m/ci-dev.yaml /m/ci-prod.yaml
infra/scripts/construir.sh "$V"; B=$(ls -t docs/evidencias/ci/build-$V-*.txt | head -1)
infra/scripts/promover.sh dev "$B"; infra/scripts/04-desplegar.sh dev
source secrets/dev.env; docker build -q -t redalimenta-tests:ci tests >/dev/null
docker run --rm --network host -v "$R/secrets/ca-dev.crt:/ca.crt:ro" -e BASE_URL=https://redalimenta-dev.172-30-0-200.sslip.io \
  -e CA_FILE=/ca.crt -e SEED_PASSWORD="$SEED_PASSWORD" redalimenta-tests:ci
echo "Candidato aprobado: $B  -> promover a prod con: infra/scripts/promover.sh prod $B && infra/scripts/04-desplegar.sh prod"
