#!/usr/bin/env bash
# Paso 3: plataforma (MetalLB, cert-manager + CA, Traefik/Gateway API). Uso: 02-plataforma.sh dev|prod
set -euo pipefail
AMB=${1:?dev|prod}; CTX=k3d-ra-$AMB
DIR=$(cd "$(dirname "$0")/../platform" && pwd); source "$DIR/versions.env"
H="helm --kube-context $CTX"
helm repo add metallb https://metallb.github.io/metallb >/dev/null; helm repo add jetstack https://charts.jetstack.io >/dev/null
helm repo add traefik https://traefik.github.io/charts >/dev/null; helm repo update >/dev/null
# MetalLB necesita privilegios (speaker con hostNetwork): excepción documentada al perfil restricted
kubectl --context $CTX create ns metallb-system --dry-run=client -o yaml | kubectl --context $CTX apply -f -
kubectl --context $CTX label ns metallb-system pod-security.kubernetes.io/enforce=privileged --overwrite
$H upgrade --install metallb metallb/metallb -n metallb-system --version $METALLB_CHART -f "$DIR/metallb-values.yaml" --wait
kubectl --context $CTX apply -f "$DIR/metallb-$AMB.yaml"
$H upgrade --install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --version $CERT_MANAGER_CHART \
   -f "$DIR/cert-manager-values.yaml" --wait
sed "s/AMBIENTE/$AMB/" "$DIR/issuers.yaml" | kubectl --context $CTX apply -f -
kubectl --context $CTX -n cert-manager wait certificate/redalimenta-lab-ca --for=condition=Ready --timeout=120s
kubectl --context $CTX create ns traefik --dry-run=client -o yaml | kubectl --context $CTX apply -f -
kubectl --context $CTX label ns traefik pod-security.kubernetes.io/enforce=restricted --overwrite
$H upgrade --install traefik traefik/traefik -n traefik --version $TRAEFIK_CHART -f "$DIR/traefik-values.yaml" --wait
kubectl --context $CTX -n traefik get svc traefik
