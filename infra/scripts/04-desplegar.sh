#!/usr/bin/env bash
# Pasos 5-7: datos, migraciones y aplicación de un ambiente desde su overlay. Uso: 04-desplegar.sh dev|prod
set -euo pipefail
AMB=${1:?dev|prod}; CTX=k3d-ra-$AMB; NS=redalimenta; R=$(cd "$(dirname "$0")/../.." && pwd)
K="kubectl --context $CTX -n $NS"
kubectl --context $CTX kustomize "$R/k8s/overlays/$AMB" > /tmp/ra-$AMB.yaml
# El Job de migraciones es inmutable: se recrea en cada despliegue (alembic es idempotente)
$K delete job migraciones --ignore-not-found >/dev/null
kubectl --context $CTX apply --server-side --force-conflicts -f /tmp/ra-$AMB.yaml > /tmp/ra-$AMB.apply.log; grep -v unchanged /tmp/ra-$AMB.apply.log || true
$K rollout status statefulset/postgres --timeout=300s
$K rollout status statefulset/mongo --timeout=300s
$K wait job/migraciones --for=condition=complete --timeout=300s
$K logs job/migraciones --tail=3
for d in backend outbox frontend; do $K rollout status deploy/$d --timeout=300s; done
# Producción: los PV de datos y respaldos pasan a Retain (local-path crea los PV con Delete). Así, borrar un PVC
# por error no borra el directorio de datos del nodo; el PV queda Released y se puede recuperar.
if [ "$AMB" = prod ]; then
  for pv in $($K get pvc -o jsonpath='{.items[*].spec.volumeName}'); do
    kubectl --context $CTX patch pv "$pv" -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}' >/dev/null
  done
  kubectl --context $CTX get pv -o custom-columns=PV:.metadata.name,RECLAIM:.spec.persistentVolumeReclaimPolicy,PVC:.spec.claimRef.name --no-headers | grep redalimenta || true
fi
$K get pods -o wide
