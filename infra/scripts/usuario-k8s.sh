#!/usr/bin/env bash
# Emite una identidad humana con certificado de cliente (CSR API) y genera su kubeconfig en secrets/ (no versionado).
# Uso: usuario-k8s.sh <dev|prod> <usuario> <grupo>   p. ej. prod ana.operadora redalimenta:operadores
set -euo pipefail
AMB=$1; U=$2; G=$3; CTX=k3d-ra-$AMB; R=$(cd "$(dirname "$0")/../.." && pwd); D="$R/secrets/usuarios"; mkdir -p "$D"; chmod 700 "$D"
openssl genpkey -algorithm ed25519 -out "$D/$U-$AMB.key" 2>/dev/null; chmod 600 "$D/$U-$AMB.key"
openssl req -new -key "$D/$U-$AMB.key" -subj "/CN=$U/O=$G" -out "$D/$U-$AMB.csr" 2>/dev/null
kubectl --context $CTX delete csr $U --ignore-not-found >/dev/null
cat <<YAML | kubectl --context $CTX apply -f - >/dev/null
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata: {name: $U}
spec:
  request: $(base64 -w0 < "$D/$U-$AMB.csr")
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 2592000
  usages: [client auth]
YAML
kubectl --context $CTX certificate approve $U >/dev/null; sleep 2
kubectl --context $CTX get csr $U -o jsonpath='{.status.certificate}' | base64 -d > "$D/$U-$AMB.crt"
SRV=$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.server}")
kubectl config view --raw -o jsonpath="{.clusters[?(@.name==\"$CTX\")].cluster.certificate-authority-data}" | base64 -d > "$D/ca-api-$AMB.crt"
KC="$D/$U-$AMB.kubeconfig"
kubectl --kubeconfig "$KC" config set-cluster ra-$AMB --server="$SRV" --certificate-authority="$D/ca-api-$AMB.crt" --embed-certs >/dev/null
kubectl --kubeconfig "$KC" config set-credentials $U --client-certificate="$D/$U-$AMB.crt" --client-key="$D/$U-$AMB.key" --embed-certs >/dev/null
kubectl --kubeconfig "$KC" config set-context $U@ra-$AMB --cluster=ra-$AMB --user=$U --namespace=redalimenta >/dev/null
kubectl --kubeconfig "$KC" config use-context $U@ra-$AMB >/dev/null; chmod 600 "$KC"; rm -f "$D/$U-$AMB.csr"
echo "kubeconfig: $KC  (CN=$U, O=$G)"
