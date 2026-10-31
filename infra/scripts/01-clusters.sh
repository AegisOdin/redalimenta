#!/usr/bin/env bash
# Paso 2: registro de imágenes, redes y clústeres independientes (dev y prod) con Calico.
set -euo pipefail
R=$(cd "$(dirname "$0")/.." && pwd); source "$R/platform/versions.env"
# Registro OCI local compartido: contiene los artefactos aprobados (mismo digest en dev y prod)
k3d registry list | grep -q ra-registry.localhost || k3d registry create ra-registry.localhost --port 127.0.0.1:5050
docker network inspect ra-dev-net >/dev/null 2>&1 || docker network create --subnet 172.30.0.0/24 --gateway 172.30.0.1 ra-dev-net
docker network inspect ra-prod-net >/dev/null 2>&1 || docker network create --subnet 172.31.0.0/24 --gateway 172.31.0.1 ra-prod-net
for AMB in ${@:-dev prod}; do
  if k3d cluster list | grep -q "^ra-$AMB "; then echo "ra-$AMB ya existe"; continue; fi
  k3d cluster create --config "$R/clusters/k3d-$AMB.yaml"
  CIDR=$([ $AMB = dev ] && echo 10.42.0.0/16 || echo 10.52.0.0/16)
  python3 "$R/platform/calico/render.py" $CALICO_VERSION $CIDR "$R/platform/calico/calico-$AMB.yaml"
  kubectl --context k3d-ra-$AMB apply --server-side -f "$R/platform/calico/calico-$AMB.yaml" >/dev/null
  kubectl --context k3d-ra-$AMB -n kube-system rollout status ds/calico-node --timeout=300s
  kubectl --context k3d-ra-$AMB wait node --all --for=condition=Ready --timeout=300s
  kubectl --context k3d-ra-$AMB get nodes -o wide
done
