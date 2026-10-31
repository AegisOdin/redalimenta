# RedAlimenta — Kubernetes para desarrollo y producción

Gestión de donativos, caducidades y entregas de un banco de alimentos comunitario (datos 100 % sintéticos).
SPA React + API FastAPI modular + PostgreSQL (fuente de verdad) + MongoDB (expediente de trazabilidad, alimentado por outbox),
desplegada en **dos clústeres k3s independientes** (k3d): `k3d-ra-dev` (1 nodo) y `k3d-ra-prod` (1 control plane + 2 workers).

| Ambiente | URL | API Kubernetes |
|---|---|---|
| Desarrollo | https://redalimenta-dev.172-30-0-200.sslip.io | 127.0.0.1:6551 (`k3d-ra-dev`) |
| Producción (lab) | https://redalimenta.172-31-0-200.sslip.io | 127.0.0.1:6552 (`k3d-ra-prod`) |

## Estructura
```
frontend/            SPA React + Vite, Nginx no root (Dockerfile, nginx.conf)
backend/             FastAPI, SQLAlchemy, Alembic (migrations/), PyMongo, worker outbox, tareas, semilla
tests/functional/    pruebas funcionales de API (pytest)      tests/seguridad/  NetworkPolicy, RBAC, permisos BD
tests/carga/         k6 + muestreo de series (HPA)            tests/fallos/     fallos, drain, BD caída, rollback
k8s/base/            manifiestos comunes (Kustomize)          k8s/overlays/{dev,prod}  configuración por ambiente
infra/clusters/      configuración k3d + política de auditoría
infra/platform/      Calico, MetalLB, cert-manager, Traefik (versiones fijadas en versions.env)
infra/firewall/      firewall de host por nodo y su validación
infra/scripts/       00..05 instalación, construir/promover, secretos, usuarios k8s, CI local
observabilidad/      kube-prometheus-stack, Loki, Alloy, panel Grafana
respaldos/           extracción fuera del clúster y restauración aislada verificada
docs/                informe (D01-D10), diagramas editables (.mmd/.dot) y evidencias
.github/workflows/   CI/CD (pruebas, kubeconform, Trivy, promoción con aprobación)
```

## Inicio rápido (desde un equipo limpio con Docker y python3)
```bash
infra/scripts/00-prerequisitos.sh          # kubectl, k3d, helm, trivy en ~/.local/bin
printf 'fs.inotify.max_user_instances=1024\nfs.inotify.max_user_watches=524288\n' | sudo tee /etc/sysctl.d/99-kubernetes-k3d.conf && sudo sysctl --system   # necesario con 4 nodos k3s
infra/scripts/01-clusters.sh               # registro OCI, redes, clústeres dev y prod, Calico
infra/scripts/02-plataforma.sh dev && infra/scripts/02-plataforma.sh prod   # MetalLB, cert-manager, Traefik
infra/scripts/05-observabilidad.sh prod    # Prometheus, Grafana, Alertmanager, Loki, Alloy
infra/scripts/construir.sh 1.0.0           # build + Trivy + push (imprime digests)
B=$(ls -t docs/evidencias/ci/build-1.0.0-*.txt | head -1)
for a in dev prod; do infra/scripts/03-secretos.sh $a; infra/scripts/promover.sh $a $B; infra/scripts/04-desplegar.sh $a; done
infra/firewall/firewall-nodos.sh prod && infra/firewall/firewall-nodos.sh dev
```
Los secretos se generan al azar en `secrets/<amb>.env` (permisos 600, **excluido de Git**); los usuarios de prueba
(`admin@redalimenta.test`, `coordinador@…`, `social@…`, `voluntario.norte@…`) usan `SEED_PASSWORD` de ese archivo.
La CA de cada ambiente queda en `secrets/ca-<amb>.crt` para confiar en el certificado HTTPS del laboratorio.

El procedimiento detallado paso a paso, la seguridad, la operación y los resultados están en `docs/informe/`.

## Operación
- Rotar la contraseña de la cuenta de la app: `infra/scripts/rotar-secreto.sh prod`
- Alta de una identidad humana con RBAC: `infra/scripts/usuario-k8s.sh prod <usuario> redalimenta:operadores`
- Respaldo manual, extracción y restauración aislada: `kubectl -n redalimenta create job r1 --from=cronjob/respaldo`, `respaldos/extraer.sh prod`, `respaldos/restaurar.sh prod backups/prod/<marca>`
- Firewall de nodos autorreparable (opcional; lo activa el administrador):
  `cp infra/firewall/systemd/redalimenta-firewall.* ~/.config/systemd/user/ && systemctl --user daemon-reload && systemctl --user enable --now redalimenta-firewall.timer` (y `sudo loginctl enable-linger $USER` para que corra sin sesión abierta)
