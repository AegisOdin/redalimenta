#!/usr/bin/env bash
# Fija en el overlay del ambiente los digests de un build (mismo artefacto en dev y prod; solo cambia configuración).
# Uso: promover.sh <dev|prod> <archivo build-*.txt>
set -euo pipefail
AMB=${1:?}; B=${2:?}; R=$(cd "$(dirname "$0")/../.." && pwd); K="$R/k8s/overlays/$AMB/kustomization.yaml"
python3 - "$K" "$B" <<'PY'
import re, sys
k, b = sys.argv[1], sys.argv[2]
s = open(k).read()
for line in open(b):
    comp, tag, dig = line.split()
    s = re.sub(rf"(name: k3d-ra-registry.localhost:5050/redalimenta-{comp}\n\s+digest: )sha256:[0-9a-f]+", rf"\g<1>{dig}", s)
open(k, "w").write(s)
PY
grep -A1 "redalimenta-" "$K" | grep digest
