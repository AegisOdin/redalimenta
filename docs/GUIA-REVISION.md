# Guía para la revisión (10 minutos)

Todo se ejecuta desde `~/Documents/Proyecto_Kubernetes/redalimenta`.

## 1. Antes del turno (20–30 min antes)

1. Conecta la laptop a la corriente y desactiva la suspensión automática. Un reinicio o una suspensión borran las reglas del firewall y los port-forwards.
2. Ejecuta `infra/scripts/preparar-revision.sh`. Todo debe salir en verde (✓). El script:
   - arranca los clústeres si están detenidos;
   - reaplica el firewall de los nodos;
   - limpia los Jobs fallidos y lanza un respaldo nuevo;
   - abre Grafana, Prometheus y Alertmanager en localhost;
   - corre las 22 pruebas funcionales en dev y prod.
3. Deja abiertas estas pestañas, en este orden:

| # | Página | Para qué |
|---|---|---|
| 1 | `docs/informe/Informe-RedAlimenta.pdf` | Informe (D01–D10) |
| 2 | https://redalimenta.172-31-0-200.sslip.io (sesión de coordinador) | App en prod |
| 3 | https://redalimenta-dev.172-30-0-200.sslip.io (otra ventana o perfil) | App en dev: se ve el aviso del ambiente |
| 4 | http://localhost:3000 → panel "RedAlimenta - Operación" | Grafana: réplicas, p95, errores, outbox |
| 5 | http://localhost:9090/alerts | Prometheus: las 10 reglas de alerta |
| 6 | Explorador de Grafana → Loki, consulta `{namespace="redalimenta"}` | Logs centralizados |
| 7 | https://github.com/AegisOdin/redalimenta/actions | CI en verde |
| 8 | Carpeta `docs/evidencias/` en VS Code | E01–E14 y SEC-01 a SEC-04 |

   Las contraseñas están en `secrets/prod.env`: `SEED_PASSWORD` para la app y `GRAFANA_ADMIN` para Grafana (usuario `admin`). Inicia sesión antes del turno. No muestres ese archivo en pantalla.
4. Abre dos terminales: una con `watch kubectl --context k3d-ra-prod -n redalimenta get pods,hpa -o wide` y otra libre para comandos.

## 2. Guion de 10 minutos (alineado a la rúbrica)

| Min | Criterio (puntos) | Qué mostrar | Comando o página |
|---|---|---|---|
| 0–1 | Proyecto y app (15) | RedAlimenta: banco de alimentos con 4 roles. En la app: alta de un lote, despensa Solicitada → Aprobada y el rastreo del lote (MongoDB) | Pestaña 2 |
| 1–2 | Arquitectura (10) | Diagramas de despliegue y red en el informe (D03) | PDF |
| 2–3 | Dos ambientes (15) | Dos clústeres independientes, prod con 1 control plane y 2 workers, Kustomize base + overlays | `kubectl config get-contexts`<br>`kubectl --context k3d-ra-prod get nodes -o wide`<br>`kubectl --context k3d-ra-dev get nodes -o wide` |
| 3–4 | Bases y respaldo (10) | PostgreSQL como fuente de verdad, MongoDB con outbox, respaldo cifrado y restauración (RTO 78 s) | `kubectl --context k3d-ra-prod -n redalimenta get sts,pvc,cronjob`<br>`docs/evidencias/E13-restauracion-prod.txt` |
| 4–5 | HPA y carga (15) | HPA de 2 a 6 réplicas, gráficas, balanceo 50/50 | `kubectl --context k3d-ra-prod -n redalimenta get hpa`<br>`docs/evidencias/carga/g1-replicas-hpa.png`, `g4-p95-comparacion.png`<br>`E07-balanceo-prod.txt` |
| 5–7 | Seguridad (15) | NetworkPolicy en vivo (30 s), RBAC (6 s), PSA restricted, HTTPS | `tests/seguridad/networkpolicy.sh`<br>`tests/seguridad/rbac.sh`<br>`kubectl --context k3d-ra-prod get ns redalimenta --show-labels` |
| 7–8 | Observabilidad (10) | Panel de Grafana, reglas de alerta, logs en Loki; alertas disparadas y resueltas | Pestañas 4–6<br>`docs/evidencias/fallos/E10-historial-alertas.txt` |
| 8–10 | Defensa y cambio en vivo (10) | Lo que pida el profesor (sección 3) y las preguntas (sección 4) | — |

No corras pruebas de carga ni `fallos.sh` durante el turno: duran de 5 a 20 minutos. Muestra sus evidencias.

## 3. Cambio en vivo: datos de prueba, respaldo y reversión

El profesor exige que todo cambio en vivo use datos de prueba, tenga un respaldo previo y un procedimiento de reversión. Esta receta cumple los tres puntos y tarda unos 2 minutos.

```bash
K="kubectl --context k3d-ra-prod -n redalimenta"
# 1) Respaldo previo
$K create job respaldo-pre-cambio --from=cronjob/respaldo && $K wait --for=condition=complete job/respaldo-pre-cambio --timeout=120s
# 2) Dato de prueba: en la app (Hogares > Nuevo) crea un hogar con clave PRUEBA-REV
# 3) Cambio: actualización gradual a 1.1.0 (compatible con el esquema actual)
$K set image deploy/backend backend=k3d-ra-registry.localhost:5050/redalimenta-backend@sha256:42225dac0603da29c8ce8cf3a010854e12b7caf0b1c208d292d65b76659f8fa5
$K rollout status deploy/backend
curl -s --cacert secrets/ca-prod.crt https://redalimenta.172-31-0-200.sslip.io/api/version   # -> 1.1.0
# 4) Reversión
$K rollout undo deploy/backend && $K rollout status deploy/backend
curl -s --cacert secrets/ca-prod.crt https://redalimenta.172-31-0-200.sslip.io/api/version   # -> 1.1.1
# 5) Verificación: el hogar PRUEBA-REV sigue en la app (el rollback de imagen no toca los datos); después dalo de baja
```

Otros cambios rápidos que puede pedir el profesor:

| Pedido | Comando |
|---|---|
| Borrar un Pod | `$K delete pod -l app.kubernetes.io/name=backend --wait=false`; en el `watch` se ve cómo lo recrea el Deployment |
| Escalar | `$K scale deploy/frontend --replicas=3`; para revertir: `$K scale deploy/frontend --replicas=2` |
| Ver logs | `$K logs deploy/backend --tail=20` |
| Restaurar un respaldo | `respaldos/extraer.sh prod` y luego `respaldos/restaurar.sh prod backups/prod/<marca>`. Restaura en un namespace aislado, nunca sobre producción (unos 80 s) |

## 4. Respuestas cortas a las preguntas de defensa

- **¿Qué ocurre desde que se abre la URL hasta las bases?**
  1. sslip.io resuelve a 172.31.0.200, la IP que anuncia MetalLB por ARP.
  2. Traefik recibe la conexión por el Gateway API y termina TLS con un certificado de cert-manager.
  3. Las HTTPRoute envían `/` al Service del frontend (Nginx) y `/api` al Service del backend.
  4. kube-proxy reparte entre las réplicas del backend.
  5. FastAPI valida el JWT y el rol, y consulta PostgreSQL por DNS (`postgres`), con TLS y verify-full.
  6. Las escrituras registran un evento en el outbox; el worker lo proyecta a MongoDB, que solo se lee para el rastreo.
  7. La NetworkPolicy solo permite los flujos entre backend, PostgreSQL y MongoDB.
- **¿Reiniciar un contenedor, recrear un Pod, escalar y añadir nodos?** Reiniciar: el kubelet relanza el contenedor en el mismo Pod, con la misma IP. Recrear: un Pod nuevo, con otra IP y posiblemente en otro nodo. Escalar: más Pods sobre los nodos que ya existen; el HPA solo hace esto. Añadir nodos aumenta la capacidad física y Kubernetes no lo hace solo.
- **¿Qué sigue funcionando si falla…?** Está en el informe, D10, en "Qué sigue funcionando ante cada fallo", con las pruebas E11.
- **¿Cómo se demuestra que lo bloqueó la política y no un servicio caído?** `networkpolicy.sh` usa controles: el mismo destino responde desde un Pod autorizado, el DNS funciona y el intento bloqueado termina en timeout, no en "connection refused".

## 5. Si algo falla durante el turno

| Síntoma | Solución |
|---|---|
| La app no carga o falta el firewall tras un reinicio | `infra/scripts/preparar-revision.sh` |
| Grafana o Prometheus no abren | Lo mismo: el script reabre los port-forwards |
| El navegador marca el certificado como no válido | Es la CA del laboratorio. Importa `secrets/ca-prod.crt` o explica que en producción real se usaría ACME |
| Un CronJob aparece `Failed` | `kubectl --context k3d-ra-prod -n redalimenta create job respaldo-manual --from=cronjob/respaldo` |
