#!/usr/bin/env bash
# Paso 1: herramientas del equipo administrador (sin sudo, en ~/.local/bin). Requiere Docker y python3.
set -euo pipefail
source "$(dirname "$0")/../platform/versions.env"
B=$HOME/.local/bin; mkdir -p "$B"; cd "$B"
[ -x kubectl ] || { curl -sLo kubectl https://dl.k8s.io/release/v1.37.2/bin/linux/amd64/kubectl; chmod +x kubectl; }
[ -x k3d ] || { curl -sLo k3d https://github.com/k3d-io/k3d/releases/download/$K3D_VERSION/k3d-linux-amd64; chmod +x k3d; }
[ -x helm ] || curl -sL https://get.helm.sh/helm-v4.3.1-linux-amd64.tar.gz | tar xz --strip-components=1 linux-amd64/helm
[ -x trivy ] || curl -sL https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz | tar xz trivy
echo "kubectl $(kubectl version --client -o json | python3 -c 'import json,sys;print(json.load(sys.stdin)["clientVersion"]["gitVersion"])')"
k3d version | head -1; helm version --short; trivy --version | head -1
# Límites recomendados del host para varios nodos k3s (requiere sudo, ver manual D05):
echo "inotify max_user_instances=$(cat /proc/sys/fs/inotify/max_user_instances) (recomendado >= 1024)"
