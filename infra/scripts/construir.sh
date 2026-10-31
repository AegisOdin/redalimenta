#!/usr/bin/env bash
# CI local: pruebas de construcción, análisis de vulnerabilidades (Trivy) y publicación con etiqueta inmutable.
# Uso: construir.sh <version>   (p. ej. 1.0.0). Imprime los digests publicados.
set -euo pipefail
V=${1:?version}; R=$(cd "$(dirname "$0")/../.." && pwd); REG=k3d-ra-registry.localhost:5050
SHA=$(git -C "$R" rev-parse --short HEAD 2>/dev/null || date -u +%Y%m%d%H%M); TAG="$V-$SHA"
mkdir -p "$R/docs/evidencias/ci"
for c in backend frontend; do
  docker build -q -t $REG/redalimenta-$c:$TAG --build-arg APP_VERSION=$V \
    --label org.opencontainers.image.version=$V --label org.opencontainers.image.revision=$SHA "$R/$c" >/dev/null
  # Hallazgos HIGH/CRITICAL con corrección disponible bloquean la publicación
  trivy image -q --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 --format table \
    --output "$R/docs/evidencias/ci/trivy-$c-$TAG.txt" $REG/redalimenta-$c:$TAG \
    || { echo "Trivy encontró vulnerabilidades corregibles en $c (ver docs/evidencias/ci)"; exit 1; }
  # Docker solo trata "localhost" como registro HTTP local; es el mismo registro que ven los nodos como $REG
  docker tag $REG/redalimenta-$c:$TAG localhost:5050/redalimenta-$c:$TAG
  docker push -q localhost:5050/redalimenta-$c:$TAG >/dev/null
  D=$(docker inspect --format '{{index .RepoDigests 0}}' localhost:5050/redalimenta-$c:$TAG | cut -d@ -f2)
  echo "$c $TAG $D"
done | tee "$R/docs/evidencias/ci/build-$TAG.txt"
