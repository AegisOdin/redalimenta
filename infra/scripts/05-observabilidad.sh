#!/usr/bin/env bash
# Observabilidad de producción: métricas, paneles, alertas y logs centralizados. Uso: 05-observabilidad.sh [prod]
set -euo pipefail
AMB=${1:-prod}; CTX=k3d-ra-$AMB; R=$(cd "$(dirname "$0")/../.." && pwd); source "$R/infra/platform/versions.env"
H="helm --kube-context $CTX"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add grafana https://grafana.github.io/helm-charts >/dev/null; helm repo update >/dev/null
kubectl --context $CTX create ns monitoring --dry-run=client -o yaml | kubectl --context $CTX apply -f -
# node-exporter y Alloy leen el host (hostNetwork/hostPath): excepción documentada al perfil restricted
kubectl --context $CTX label ns monitoring pod-security.kubernetes.io/enforce=privileged --overwrite
F="$R/secrets/$AMB.env"; grep -q GRAFANA_ADMIN "$F" || echo "GRAFANA_ADMIN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(18))')" >> "$F"
source "$F"
kubectl --context $CTX -n monitoring create secret generic grafana-admin --from-literal=admin-user=admin \
  --from-literal=admin-password="$GRAFANA_ADMIN" --dry-run=client -o yaml | kubectl --context $CTX apply -f - >/dev/null
$H upgrade --install kps prometheus-community/kube-prometheus-stack -n monitoring --version $KPS_CHART -f "$R/observabilidad/kps-values.yaml" --wait --timeout 10m
$H upgrade --install loki grafana/loki -n monitoring --version $LOKI_CHART -f "$R/observabilidad/loki-values.yaml" --wait --timeout 10m
$H upgrade --install alloy grafana/alloy -n monitoring --version $ALLOY_CHART -f "$R/observabilidad/alloy-values.yaml" --wait
# cert-manager expone métricas de expiración de certificados
$H upgrade cert-manager jetstack/cert-manager -n cert-manager --version $CERT_MANAGER_CHART --reuse-values \
   --set prometheus.servicemonitor.enabled=true --wait
kubectl --context $CTX apply -f "$R/observabilidad/dashboards/" -f "$R/observabilidad/monitores/"
kubectl --context $CTX -n monitoring get pods
