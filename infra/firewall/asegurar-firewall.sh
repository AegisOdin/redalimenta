#!/usr/bin/env bash
# Reaplica RA-FW en cualquier nodo k3d que lo haya perdido (reinicio o recreación del contenedor-nodo).
# Pensado para el timer de systemd de usuario infra/firewall/systemd/redalimenta-firewall.timer (instalación manual, ver README).
set -uo pipefail
D=$(cd "$(dirname "$0")" && pwd); export PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin
for AMB in dev prod; do
  for n in $(docker ps --filter label=k3d.cluster=ra-$AMB --format '{{.Names}} {{.Label "k3d.role"}}' 2>/dev/null | awk '$2=="server"||$2=="agent"{print $1}'); do
    if ! docker exec "$n" iptables -C INPUT -j RA-FW >/dev/null 2>&1; then
      echo "$(date -Is) $n sin RA-FW: reaplicando firewall de $AMB"; "$D/firewall-nodos.sh" "$AMB"; break
    fi
  done
done
