#!/usr/bin/env python3
"""Genera el manifiesto de Calico (versión fijada) adaptado a k3s/k3d:
 - IPPool con el CIDR de Pods del ambiente, encapsulación VXLAN (sin BGP/BIRD)
 - container_settings.allow_ip_forwarding=true (requerido por k3s dentro de contenedores)
Uso: render.py <version> <pod_cidr> <salida>"""
import re
import sys
import urllib.request

ver, cidr, out = sys.argv[1:4]
url = f"https://raw.githubusercontent.com/projectcalico/calico/{ver}/manifests/calico.yaml"
y = urllib.request.urlopen(url).read().decode()
y = y.replace('calico_backend: "bird"', 'calico_backend: "vxlan"')
y = re.sub(r'(- name: CALICO_IPV4POOL_IPIP\n\s+value: )"Always"', r'\1"Never"', y)
y = re.sub(r'(- name: CALICO_IPV4POOL_VXLAN\n\s+value: )"Never"', r'\1"Always"', y)
y = y.replace('# - name: CALICO_IPV4POOL_CIDR\n            #   value: "192.168.0.0/16"',
              f'- name: CALICO_IPV4POOL_CIDR\n              value: "{cidr}"')
y = y.replace('          "type": "calico",\n', '          "type": "calico",\n          "container_settings": {"allow_ip_forwarding": true},\n', 1)
y = re.sub(r"^\s*- --?bird-(live|ready)\n", "", y, flags=re.M)  # VXLAN: sin BIRD en las sondas
assert not re.search(r"- --?bird-(live|ready)", y) and f'value: "{cidr}"' in y and "allow_ip_forwarding" in y and 'calico_backend: "vxlan"' in y
open(out, "w").write(y)
print("ok", out)
