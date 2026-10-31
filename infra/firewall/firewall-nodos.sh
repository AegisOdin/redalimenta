#!/usr/bin/env bash
# Firewall de host en cada nodo del clúster (iptables dentro del contenedor-nodo k3d).
# Cadena propia RA-FW (INPUT) y RA-FW-PRE (mangle/PREROUTING para el rango NodePort).
# Idempotente: vacía y recrea las cadenas. Uso: firewall-nodos.sh dev|prod [quitar]
set -euo pipefail
AMB=${1:?dev|prod}; ACCION=${2:-aplicar}
NET=ra-$AMB-net; GW=$(docker network inspect $NET -f '{{(index .IPAM.Config 0).Gateway}}')
POD_CIDR=$([ $AMB = dev ] && echo 10.42.0.0/16 || echo 10.52.0.0/16)
NODOS=$(docker ps --filter label=k3d.cluster=ra-$AMB --filter label=k3d.role=server --format '{{.Names}}'; \
        docker ps --filter label=k3d.cluster=ra-$AMB --filter label=k3d.role=agent --format '{{.Names}}')
ip_de() { docker inspect -f "{{(index .NetworkSettings.Networks \"$NET\").IPAddress}}" "$1"; }
IPS_NODOS=$(for n in $NODOS; do ip_de $n; done | paste -sd, -)
LB=$(ip_de k3d-ra-$AMB-serverlb)        # balanceador de la API (único camino desde 127.0.0.1:655x)
echo "nodos=$IPS_NODOS serverlb=$LB gateway(admin host)=$GW pods=$POD_CIDR"
for n in $NODOS; do
  docker exec -i $n sh -s <<EOS
set -e
iptables -D INPUT -j RA-FW 2>/dev/null || true
iptables -F RA-FW 2>/dev/null || true; iptables -X RA-FW 2>/dev/null || true
iptables -t mangle -D PREROUTING -j RA-FW-PRE 2>/dev/null || true
iptables -t mangle -F RA-FW-PRE 2>/dev/null || true; iptables -t mangle -X RA-FW-PRE 2>/dev/null || true
[ "$ACCION" = quitar ] && { echo "$n: reglas retiradas"; exit 0; }
iptables -N RA-FW
# 1-3 tráfico ya establecido, loopback y tráfico de Pods (lo gobiernan las NetworkPolicy de Calico)
iptables -A RA-FW -m conntrack --ctstate ESTABLISHED,RELATED -m comment --comment "01 establecidas" -j RETURN
iptables -A RA-FW -i lo -m comment --comment "02 loopback" -j RETURN
iptables -A RA-FW -i cali+ -m comment --comment "03 Pods locales (NetworkPolicy)" -j RETURN
iptables -A RA-FW -i vxlan.calico -m comment --comment "03 Pods remotos VXLAN" -j RETURN
# 4 encapsulación VXLAN de Calico solo entre nodos
iptables -A RA-FW -p udp --dport 4789 -s $IPS_NODOS -m comment --comment "04 VXLAN Calico entre nodos" -j RETURN
# 5 plano de control/kubelet/memberlist/métricas solo entre nodos
iptables -A RA-FW -p tcp -m multiport --dports 6443,6444,10250,7946,9100,9099 -s $IPS_NODOS -m comment --comment "05 control plane, kubelet, MetalLB, node-exporter entre nodos" -j RETURN
iptables -A RA-FW -p udp --dport 7946 -s $IPS_NODOS -m comment --comment "05 memberlist MetalLB" -j RETURN
# 6 API solo vía el balanceador local (administración desde 127.0.0.1 del equipo administrador)
iptables -A RA-FW -p tcp --dport 6443 -s $LB -m comment --comment "06 API desde serverlb (red de administración)" -j RETURN
# 7 Pods del nodo hacia kubelet/node-exporter (metrics-server, Prometheus)
iptables -A RA-FW -p tcp -m multiport --dports 6443,10250,9100 -s $POD_CIDR -m comment --comment "07 Pods hacia servicios del nodo" -j RETURN
iptables -A RA-FW -p icmp -s $IPS_NODOS -m comment --comment "08 ICMP entre nodos" -j RETURN
# 9 resto: registrar y descartar
iptables -A RA-FW -m comment --comment "99 descartar resto" -j DROP
iptables -I INPUT 1 -j RA-FW
# NodePort: solo la entrada web publicada por MetalLB (80/443) es accesible desde fuera de los nodos
iptables -t mangle -N RA-FW-PRE
iptables -t mangle -A RA-FW-PRE -s $IPS_NODOS -m comment --comment "10 tráfico entre nodos" -j RETURN
iptables -t mangle -A RA-FW-PRE -p tcp --dport 30000:32767 -m addrtype --dst-type LOCAL -m comment --comment "11 NodePort cerrado a externos" -j DROP
iptables -t mangle -I PREROUTING 1 -j RA-FW-PRE
echo "$n: firewall aplicado"
EOS
done
