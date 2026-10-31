#!/usr/bin/env bash
# Copia fuera del clúster el último respaldo (destino separado del volumen y del clúster de origen).
# Uso: extraer.sh dev|prod   -> backups/<amb>/<marca>/ (directorio ignorado por Git, permisos 700)
set -euo pipefail
AMB=${1:?}; K="kubectl --context k3d-ra-$AMB -n redalimenta"; R=$(cd "$(dirname "$0")/.." && pwd)
$K delete pod lector-respaldos --ignore-not-found --wait >/dev/null
$K run lector-respaldos --image=mongo:9.0.4 --restart=Never --overrides='{"spec":{"automountServiceAccountToken":false,
 "securityContext":{"runAsNonRoot":true,"runAsUser":999,"runAsGroup":999,"fsGroup":999,"seccompProfile":{"type":"RuntimeDefault"}},
 "containers":[{"name":"c","image":"mongo:9.0.4","command":["sleep","900"],"securityContext":{"allowPrivilegeEscalation":false,"capabilities":{"drop":["ALL"]}},
 "volumeMounts":[{"name":"r","mountPath":"/respaldos","readOnly":true}]}],"volumes":[{"name":"r","persistentVolumeClaim":{"claimName":"respaldos"}}]}}' >/dev/null
$K wait pod/lector-respaldos --for=condition=Ready --timeout=120s >/dev/null
M=$($K exec lector-respaldos -- sh -c 'ls -1d /respaldos/2* | tail -1'); N=$(basename "$M")
D="$R/backups/$AMB/$N"; mkdir -p "$D"; chmod 700 "$R/backups"
for f in $($K exec lector-respaldos -- ls "$M"); do $K exec lector-respaldos -- cat "$M/$f" > "$D/$f"; done
$K delete pod lector-respaldos --wait=false >/dev/null
( cd "$D" && sha256sum -c postgres.sha256 mongo.sha256 )
echo "$D"
