# Guía para la revisión (10 minutos)

Todo se ejecuta desde `~/Documents/Proyecto_Kubernetes/redalimenta`. Los comandos de esta guía se probaron el 2026-11-03 sobre los clústeres en ejecución.

Atajo que usan los comandos de abajo. Pégalo una vez en cada terminal:

```bash
cd ~/Documents/Proyecto_Kubernetes/redalimenta
K="kubectl --context k3d-ra-prod -n redalimenta"
PROD=https://redalimenta.172-31-0-200.sslip.io
DEV=https://redalimenta-dev.172-30-0-200.sslip.io
```

---

admin@redalimenta.test 

## 1. Antes del turno (20–30 min antes)

1. Conecta la laptop a la corriente y desactiva la suspensión automática. Un reinicio o una suspensión borran las reglas del firewall y cierran los port-forwards.
2. Corre el script de preparación. Todo debe salir con ✓:
   ```bash
   infra/scripts/preparar-revision.sh
   ```
   El script:
   - arranca los clústeres;
   - reaplica el firewall y comprueba la cadena RA-FW en cada nodo;
   - limpia los Jobs fallidos y lanza un respaldo nuevo;
   - abre Grafana (3000), Prometheus (9090) y Alertmanager (9093);
   - corre las 22 pruebas funcionales en dev y prod.
3. Inicia las sesiones **antes** del turno, para que ninguna contraseña aparezca en pantalla. Para ver las contraseñas en la terminal (sin abrir el archivo):
   ```bash
   grep -E '^(SEED_PASSWORD|GRAFANA_ADMIN)=' secrets/prod.env; grep '^SEED_PASSWORD=' secrets/dev.env
   ```
   Cierra `secrets/prod.env` en VS Code antes de compartir pantalla.
4. Abre estas pestañas en este orden:

| # | Página | Sesión | Para qué |
|---|---|---|---|
| 1 | `docs/informe/Informe-RedAlimenta.pdf` | — | Informe D01–D10 |
| 2 | https://redalimenta.172-31-0-200.sslip.io | `coordinador@redalimenta.test` | App en prod |
| 3 | https://redalimenta-dev.172-30-0-200.sslip.io (ventana de incógnito) | `social@redalimenta.test` | App en dev (aquí se crean los datos de prueba) |
| 4 | http://localhost:3000/d/redalimenta-op | `admin` | Panel de Grafana |
| 5 | http://localhost:9090/targets | — | Prometheus: qué se vigila |
| 6 | http://localhost:9090/alerts (página 2) | — | Las 10 reglas propias |
| 7 | https://github.com/AegisOdin/redalimenta/actions | — | CI en verde |
| 8 | Carpeta `docs/evidencias/` en VS Code | — | E01–E14 y SEC-01 a SEC-04 |

5. Abre dos terminales:
   - Terminal A, fija a la vista: `watch -n2 kubectl --context k3d-ra-prod -n redalimenta get pods,hpa -o wide`
   - Terminal B: para los comandos.
6. Navega un poco por la app de prod (lotes, despensas, rastreo) 5 minutos antes. Así los paneles de Grafana tienen movimiento.

---

## 2. Guion de 10 minutos

Usa el guion como base; si el profesor pide otra cosa, salta a la sección correspondiente.

| Min | Criterio (puntos) | Qué mostrar | Sección |
|---|---|---|---|
| 0–1 | Proyecto y app (15) | Problema, 4 roles, una regla en vivo y el rastreo | 3.1 |
| 1–2 | Arquitectura (10) | Diagramas del informe (D03) | 3.2 |
| 2–3 | Dos ambientes (15) | Dos clústeres, prod 1+2, Kustomize, imagen por digest | 3.3 |
| 3–4 | Bases y respaldo (10) | PostgreSQL, MongoDB y outbox, respaldo cifrado, restauración | 3.4 |
| 4–5 | HPA y carga (15) | HPA, gráficas de carga, balanceo en vivo | 3.5 |
| 5–7 | Seguridad (15) | NetworkPolicy, RBAC, PSA, HTTPS, firewall, secretos | 3.6 |
| 7–8 | Observabilidad (10) | Grafana, Prometheus, logs con request_id, alertas | 3.7 |
| 8–10 | Defensa y cambio en vivo (10) | Lo que pida el profesor | 4 y 5 |

No corras pruebas de carga ni `tests/fallos/fallos.sh` durante el turno, porque duran de 5 a 20 minutos. Muestra sus evidencias.

---

## 3. Qué remarcar y cómo probarlo, por criterio

### 3.1 Proyecto original y aplicación multicapa (15 pts)

**Qué remarcar.**
- RedAlimenta es un banco de alimentos con 4 roles: admin, coordinador, trabajador social y voluntario. La autorización se valida **en el servidor**, no solo en la interfaz.
- Desde la 1.1.2 el **administrador puede hacer todo** (decisión 9 del informe). Si te preguntan: es el responsable final y debe poder cubrir cualquier función; a cambio se pierde la separación de funciones, que se mitiga porque cada transición registra quién la hizo y queda en la bitácora. Las reglas de negocio se le aplican igual.
- Las 6 reglas de negocio propias son FEFO, Prioritario, merma, 14 días entre despensas, alérgenos y cadena de frío, más el retiro sanitario.
- Una despensa pasa por los estados Solicitada → Aprobada → En preparación → Lista → Entregada.
- El navegador nunca habla con las bases; solo con la API.

Haz las pruebas en **dev**, para no ensuciar prod.

**Prueba A: cadena de frío (unos 40 s).** Usuario `coordinador@` en dev.
1. Ve a Lotes → **+ Recibir donativo**. Elige un producto refrigerado ("Yogur natural 1 kg"), cualquier donante, cantidad 10 y caducidad dentro de un mes. Guarda.
2. En el lote nuevo pulsa **Inspeccionar** y escribe una temperatura de **7** °C.
3. Resultado esperado: el lote queda **Rechazado** con un motivo de cadena de frío, porque está por encima de 5 °C.

**Prueba B: Prioritario por caducidad.** Repite el paso 1 con un producto no refrigerado ("Arroz 1 kg") y una caducidad a **2 días**. Al inspeccionarlo queda **Prioritario**, porque le quedan 3 días o menos y solo puede ir en despensas que salen en las próximas 48 h.

**Prueba C: lote caducado.** Repite el paso 1 con una caducidad de ayer. La app debe rechazar el alta con un mensaje de error.

**Prueba D: 14 días y raciones.** Usuario `social@` en dev.
1. En Hogares busca uno con la columna **Elegible = No**, que recibió despensa hace menos de 14 días. Intenta registrarle una solicitud. Error esperado: "El hogar recibió despensa el …; vuelve a ser elegible el …".
2. Pulsa **+ Registrar hogar** con la clave `PRUEBA-REV` y 3 integrantes. El formulario muestra **2 raciones** (1 + 0.5 por integrante adicional, tope de 4).

**Prueba E: flujo de estados, FEFO y alérgenos.**
1. Como `social@`, aprueba una despensa Solicitada.
2. Como `coordinador@`, pulsa **Armar (FEFO)**. El sistema asigna primero los lotes que caducan antes y omite los productos con alérgenos del hogar; lo indica en pantalla.
3. Si intentas **Agregar lote manualmente** un lote que caduca después, responde "FEFO: debe usarse primero el lote …".

**Prueba F: roles.** Entra como `voluntario.norte@redalimenta.test`. Solo ve las despensas de la ruta Norte y no puede registrar lotes. Los permisos, las reglas y la seguridad de sesión están cubiertos por 22 pruebas automáticas. Córrelas en vivo (unos 5 s) para que se vea el nombre de cada una:
```bash
docker run --rm --network host -u "$(id -u)" -v "$PWD/secrets/ca-prod.crt:/ca.crt:ro" -e BASE_URL=$PROD -e CA_FILE=/ca.crt \
  -e SEED_PASSWORD="$(grep '^SEED_PASSWORD=' secrets/prod.env | cut -d= -f2-)" redalimenta-tests:dev -vv 2>&1 | grep -E "PASSED|FAILED|SKIPPED|passed" | sed 's/.*:://'
```
Este comando no imprime la contraseña: la lee del archivo directamente.

**Prueba G: rastreo (MongoDB).**
1. Ve a Rastreo y busca un lote que hayas creado en la prueba A.
2. Se ve el expediente con su checklist, temperatura y línea de tiempo. El estado coincide con PostgreSQL.

Aviso: en los datos de ejemplo algunos lotes muestran "entregado" antes de "recibido". Es un error de la semilla sintética, no de la app. Usa un lote creado en vivo.

### 3.2 Arquitecturas justificadas (10 pts)

**Qué remarcar.**
- Las tres capas: React con Nginx, FastAPI, y PostgreSQL más MongoDB.
- La entrada: MetalLB, Traefik con Gateway API y cert-manager.
- Por qué k3s y no kubeadm o minikube, y por qué Traefik y no ingress-nginx: está en D02 del informe.
- Los límites de un clúster de contenedores en un solo equipo, que la práctica permite si se explican: D03, "Puntos únicos de fallo".

**Cómo mostrarlo.** En el PDF:
- D03 trae los diagramas de despliegue de prod y de red y comunicación.
- D02 trae la tabla de comparación de tecnologías.

Explica el diagrama de red con la respuesta 4.1 de la sección de preguntas.

### 3.3 Dos ambientes reproducibles y configuración declarativa (15 pts)

**Qué remarcar.**
- Son dos clústeres **independientes**, no dos namespaces del mismo clúster.
- Prod tiene 1 control plane con taint y 2 workers.
- Base común más overlays de Kustomize: dev y prod solo difieren en configuración.
- Prod despliega **el mismo digest** que se aprobó en dev.
- Prod se reconstruyó desde cero en 12 min 3 s (E14).

**Paso a paso.**
```bash
kubectl config get-contexts | grep ra-                      # 2 contextos: k3d-ra-dev y k3d-ra-prod
kubectl --context k3d-ra-prod get nodes -o wide             # 1 control-plane + 2 workers
kubectl --context k3d-ra-dev  get nodes -o wide             # 1 nodo
kubectl --context k3d-ra-prod describe node k3d-ra-prod-server-0 | grep Taints   # NoSchedule
ls k8s/base k8s/overlays/dev k8s/overlays/prod              # base + overlays
$K get deploy -o custom-columns=NOMBRE:.metadata.name,IMAGEN:.spec.template.spec.containers[0].image
#   -> backend y frontend usan @sha256:..., no una etiqueta "latest"
tests/seguridad/independencia.sh                            # 1 s: URL, CA, secretos y volúmenes distintos
```
Evidencias: `docs/evidencias/E01-contextos-nodos.txt` y `E14-reconstruccion-prod.txt`, donde está la línea `TIEMPO_TOTAL=723s`.

Para el CI, muestra la pestaña de GitHub Actions. Los jobs `pruebas`, `manifiestos` e `imagenes` pasaron, y la promoción a prod exige aprobación manual.

### 3.4 Ambas bases, persistencia y restauración (10 pts)

**Qué remarcar.**
- **PostgreSQL es la fuente de verdad**: inventario, hogares, despensas y usuarios.
- **MongoDB guarda el expediente** de cada lote, que tiene un checklist distinto según la categoría y una línea de tiempo.
- No hay transacción entre las dos bases. Se usa el **patrón outbox**: el evento se guarda en PostgreSQL dentro de la misma transacción, y un worker lo proyecta a MongoDB de forma idempotente por `event_id`.
- Si MongoDB cae, la app sigue funcionando, el outbox acumula eventos y luego los drena sin duplicados (E11).
- Respaldo diario a las 02:00, cifrado con AES-256 y en un PVC separado.
- La restauración se probó en un namespace aislado: RTO de 78 s y RPO de 24 h.

**Paso a paso.**
```bash
$K get sts,pvc                                              # postgres-0, mongo-0 y sus volúmenes
$K get cronjob respaldo                                     # 02:00 America/Mexico_City
$K get jobs | grep respaldo                                 # último respaldo Complete
curl -s localhost:9090/api/v1/query --data-urlencode 'query=redalimenta_outbox_pendientes'   # valor "0"
```
Evidencias:
- `E04-ambos-motores.txt`
- `E13-respaldo-dev.txt`
- `E13-restauracion-prod.txt`: conteos idénticos y RTO
- `fallos/E11-mongo-caido.txt`: 0 errores y 0 duplicados

En prod, los volúmenes de datos y respaldos tienen la política `Retain`: borrar un PVC por error no borra los datos. Compruébalo con:
```bash
kubectl --context k3d-ra-prod get pv -o custom-columns=PVC:.spec.claimRef.name,POLITICA:.spec.persistentVolumeReclaimPolicy,NODO:.spec.nodeAffinity.required.nodeSelectorTerms[0].matchExpressions[0].values[0]
```
La tabla completa de volúmenes por ambiente está en el informe, D09.

Si el profesor pide restaurar en vivo (unos 2 min):
```bash
respaldos/extraer.sh prod                                   # copia el respaldo cifrado a backups/prod/<marca>
respaldos/restaurar.sh prod backups/prod/<marca>            # restaura en el namespace "restauracion", nunca sobre prod
```

### 3.5 Balanceo, HPA y pruebas de carga (15 pts)

**Qué remarcar.**
- El HPA escala el backend de 2 a 6 réplicas según CPU, con un objetivo del 60 %.
- En la prueba de carga subió de 2 a 6 y volvió a 2. Con HPA, el p95 fue de 99.7 ms; con 2 réplicas fijas, de 150 ms. Hubo 0 % de errores.
- El primer intento falló: 4 réplicas quedaron en Pending por el topologySpread. Se corrigió con `nodeTaintsPolicy: Honor`. Reportar un fallo y su corrección cuenta a favor.
- Los PDB garantizan al menos 1 réplica durante un drain.

**Paso a paso.**
```bash
$K get hpa backend                                          # 2/6, objetivo cpu 60 %
$K get pdb
$K get pods -l app.kubernetes.io/name=backend -o wide       # una réplica en cada worker
```
**Balanceo en vivo (5 s).** Manda 20 solicitudes con un identificador y cuenta cuál réplica atendió cada una:
```bash
for i in $(seq 20); do curl -s -o /dev/null --cacert secrets/ca-prod.crt -H "X-Request-ID: balanceo-$i" $PROD/api/version; done
$K logs -l app.kubernetes.io/name=backend --tail=300 --prefix | grep -o 'pod/backend-[a-z0-9-]*.*"request_id": "balanceo-' | cut -d/ -f2 | sort | uniq -c
#   -> 10 en una réplica y 10 en la otra
```
Evidencias en `docs/evidencias/carga/`:

| Archivo | Qué muestra |
|---|---|
| `g1-replicas-hpa.png` | Réplicas durante la carga |
| `g2-cpu-hpa.png` | CPU durante la carga |
| `g3-rps-comparacion.png` | Solicitudes por segundo, con HPA y sin HPA |
| `g4-p95-comparacion.png` | Latencia p95, con HPA y sin HPA |
| `g0-intento1-pending.png` | El primer intento fallido |
| `herramienta.txt` | Versión de k6 |
| `ejecucion-v2.log` | Bitácora de la corrida |
| `E07-balanceo-prod.txt` | Balanceo |

El escenario está en `tests/carga/escenario.js` y `tests/carga/ejecutar.sh`. Duración: 5 min de línea base y una rampa de 12 min.

### 3.6 Seguridad de aplicación, datos, red e infraestructura (15 pts)

**Qué remarcar, por capa.**

| Capa | Control | Cómo probarlo |
|---|---|---|
| Aplicación | JWT en cookie HttpOnly, Secure y SameSite=Strict; CSRF; Argon2id; límite de intentos; sesión que expira | Pruebas `test_token_manipulado`, `test_csrf_obligatorio`, `test_login_invalido` (prueba F) y `E03-sesion-expirada-prod.txt` |
| Transporte | HTTPS obligatorio (HTTP → 301), HSTS y cabeceras de seguridad; TLS también hacia las bases | Comandos de abajo |
| Red | NetworkPolicy que niega todo por defecto y abre solo los flujos necesarios | `tests/seguridad/networkpolicy.sh` (30 s) |
| Kubernetes | RBAC por grupos (lector, operador, desplegador); PSA restricted; ServiceAccounts sin token | Comandos de abajo |
| Datos | Usuarios de base con mínimo privilegio; Secrets cifrados en reposo (aescbc); respaldos cifrados | `tests/seguridad/rbac.sh` (6 s) |
| Infraestructura | Firewall en los nodos: solo pasan la API y la entrada web | `infra/firewall/validar-firewall.sh` (25 s) |
| Suministro | Trivy bloquea vulnerabilidades HIGH/CRITICAL; el primer build fue rechazado y corregido | `docs/evidencias/ci/trivy-*` |

**Paso a paso.**
```bash
# HTTPS y cabeceras
curl -sI http://redalimenta.172-31-0-200.sslip.io/ | grep -iE "^HTTP|^location"          # 301 -> https
curl -sI --cacert secrets/ca-prod.crt $PROD/ | grep -iE "strict-transport|content-security|x-frame|x-content"

# NetworkPolicy: PERMITIDA / BLOQUEADA, con controles
tests/seguridad/networkpolicy.sh 2>&1 | grep -E "PERMITIDA|BLOQUEADA"

# RBAC con usuarios reales (certificados emitidos por la CSR API)
KUBECONFIG=secrets/usuarios/luis.lector-prod.kubeconfig  kubectl -n redalimenta auth can-i get pods      # yes
KUBECONFIG=secrets/usuarios/luis.lector-prod.kubeconfig  kubectl -n redalimenta auth can-i delete pods   # no
KUBECONFIG=secrets/usuarios/ana.operadora-prod.kubeconfig kubectl -n redalimenta auth can-i get secrets  # no
tests/seguridad/rbac.sh                                     # también prueba los permisos de los usuarios de PostgreSQL y MongoDB

# Pod Security Admission: un Pod privilegiado es rechazado
kubectl --context k3d-ra-prod get ns redalimenta --show-labels | tr ',' '\n' | grep pod-security
$K run privilegiado --image=busybox:1.37 --privileged --dry-run=server -- sleep 1   # Forbidden: violates PodSecurity "restricted"

# Secrets cifrados en reposo
docker exec k3d-ra-prod-server-0 k3s secrets-encrypt status | head -3                 # Encryption Status: Enabled

# Firewall de nodos
infra/firewall/validar-firewall.sh 2>&1 | tail -12          # BLOQUEADO para orígenes no autorizados; la API y HTTPS responden
```
Evidencias:
- `E08-networkpolicy-prod.txt`, `E08-firewall-validacion.txt`, `E09-rbac-y-bd.txt`
- `SEC-01-cifrado-auditoria.txt` a `SEC-04-rotacion-secreto.txt`. La SEC-04 es una rotación de contraseña en vivo con 0 errores.

### 3.7 Observabilidad, alertas y respuesta a fallos (10 pts)

**Cómo funciona.**
- **Prometheus** consulta cada 30 s la ruta `/metrics` de cada componente y guarda los números: backend, outbox, exportadores de PostgreSQL y MongoDB, nodos y Kubernetes. Con ellos evalúa las reglas de alerta. Si una se cumple, la pasa a **Alertmanager**.
- **Loki** recibe los logs de todos los Pods; Alloy los recolecta en cada nodo.
- **Grafana** no guarda datos: consulta a Prometheus y a Loki y los dibuja.

**Qué remarcar.**
- Se mide la **aplicación**, no solo el clúster: latencia p95, errores 5xx, solicitudes por código y pendientes del outbox.
- Los logs están en JSON y llevan un `request_id` que viaja en la cabecera `X-Request-ID`.
- Hay 10 alertas con umbral y severidad justificados (tabla en D08). Durante las pruebas de fallos se dispararon y resolvieron 6.

**Paso a paso.**
1. **Grafana**, pestaña 4, panel "RedAlimenta - Operación". Recórrelo de arriba abajo:
   - **Aplicación:** solicitudes por segundo, p95, tasa de errores, réplicas del HPA, y CPU y memoria por Pod.
   - **Bases de datos:** disponibilidad, conexiones, transacciones y outbox.
   - **Infraestructura:** CPU y memoria por nodo, antigüedad del último respaldo, alertas activas y logs.
   - **Nodos y Kubernetes:** nodos Ready, disco y red por nodo, Pods Pending, réplicas deseadas frente a disponibles y eventos de Kubernetes.
   - **Entrada, TLS y seguridad:** solicitudes de Traefik por código, réplicas de la entrada, días para que expire cada certificado y rechazos 401/403/429.
   - **PostgreSQL y respaldos:** duración máxima de transacción, conexiones frente al máximo, Jobs de respaldo exitosos y fallidos, horas desde la última ejecución, y tamaño y duración por motor.

   Estas tres últimas secciones cubren uno por uno los objetos de la tabla "Cobertura mínima" de la sección 10 de la práctica. La correspondencia está en el informe, D08.
2. **Prometheus**, pestaña 5 (`/targets`): todos los objetivos están en **UP**, incluidos los 2 backends, el outbox y los exportadores.
3. **Prometheus**, pestaña 6 (`/alerts`): los grupos `redalimenta.disponibilidad`, `redalimenta.errores` y `redalimenta.capacidad` están en la página 2. El buscador filtra por **nombre de regla**: escribe `Respaldo` o `Outbox`. Abre una regla para enseñar su expresión y su umbral.
4. **Consulta en vivo.** En http://localhost:9090/query escribe `redalimenta_outbox_pendientes` (debe ser 0) o `pg_up` (1 = PostgreSQL arriba).
5. **Correlación de un request.** En la terminal B:
   ```bash
   curl -s -D - -o /dev/null --cacert secrets/ca-prod.crt -H "X-Request-ID: revision-demo-01" $PROD/api/version | grep -i x-request-id
   $K logs -l app.kubernetes.io/name=backend --tail=200 --prefix | grep revision-demo-01
   ```
   Luego, en Grafana → Explore → Loki, consulta `{namespace="redalimenta"} |= "revision-demo-01"`. Aparece la misma línea, centralizada.
6. **Alertas que funcionan.** En vivo solo debe estar activa `Watchdog`, que siempre se dispara a propósito para comprobar que la cadena de alertas está viva. La prueba de que las demás funcionan está en `docs/evidencias/fallos/E10-historial-alertas.txt` y `E10-alertas-activas-alertmanager.txt`.
7. **Respuesta a fallos en vivo (unos 30 s).** Borra un Pod y míralo en la terminal A y en Grafana:
   ```bash
   $K delete $($K get pod -l app.kubernetes.io/name=backend -o name | head -1) --wait=false   # borra UNA sola réplica
   ```
   El Deployment lo recrea, el Service deja de enviarle tráfico mientras no está listo, y la app no se cae porque queda la otra réplica.

Resultados de fallos medidos (D10 y `docs/evidencias/fallos/`):

| Prueba | Resultado |
|---|---|
| Pod del backend | 0 errores |
| Drain de un worker | 0 errores tras la corrección; el primer intento tuvo 34 s de corte |
| PostgreSQL caído | 99 s de error 503, como se esperaba |
| MongoDB caído | 0 errores y 0 duplicados |
| Actualización y rollback | 0 errores tras agregar preStop; el primer intento tuvo 5 errores 502 |

### 3.8 Documentación, evidencias y defensa (10 pts)

- **"¿Dónde se controla X?"** La práctica dice que el profesor puede pedirte localizar el recurso que controla un comportamiento. La respuesta está en el informe, **Anexo C**: tabla de comportamiento → archivo, por ejemplo HPA → `k8s/overlays/prod/hpa-pdb.yaml` y puertos del nodo → `infra/firewall/firewall-nodos.sh`.
- **Registro de evidencias y bitácora** (informe, D10): cada evidencia tiene fecha, ambiente, comando, resultado esperado y observado; cada prueba, precondiciones, pasos, duración y mediciones, incluidos los intentos fallidos.
- **Manual de instalación** (D05): cada paso sigue la plantilla de la práctica y está separado en desarrollo y producción.
- **Diccionario de datos** (Anexo B) y **consultas representativas** de SQL y MongoDB (D04).

- El informe está en PDF y en DOCX: `docs/informe/`. Contiene D01–D10.
- Cada evidencia E01–E14 está en `docs/evidencias/` y sus scripts en `tests/`, así que son reproducibles.
- La entrega está en la etiqueta `v1.1.2-entrega` del repositorio de GitHub (artefacto 1.1.2 en dev y prod).
- Los intentos fallidos se documentaron, no se ocultaron: HPA en Pending, corte en el drain, 502 sin preStop y build rechazado por Trivy.

---

## 4. Respuestas cortas a las preguntas de defensa

**4.1 ¿Qué ocurre desde que se abre la URL hasta las bases?**
1. sslip.io resuelve a 172.31.0.200, la IP que anuncia MetalLB por ARP.
2. Traefik recibe la conexión por el Gateway API y termina TLS con un certificado de cert-manager.
3. Las HTTPRoute envían `/` al Service del frontend (Nginx) y `/api` al Service del backend.
4. kube-proxy reparte entre las réplicas del backend.
5. FastAPI valida el JWT y el rol, y consulta PostgreSQL por DNS (`postgres`), con TLS y verify-full.
6. Las escrituras registran un evento en el outbox, y el worker lo proyecta a MongoDB, que solo se lee para el rastreo.
7. La NetworkPolicy solo permite los flujos entre backend, PostgreSQL y MongoDB.

**4.2 ¿Qué diferencia hay entre reiniciar un contenedor, recrear un Pod, escalar y añadir nodos?**
- Reiniciar: el kubelet relanza el contenedor dentro del mismo Pod, que conserva su IP.
- Recrear: se crea un Pod nuevo, con otra IP y posiblemente en otro nodo.
- Escalar: se crean más Pods sobre los nodos existentes; el HPA solo hace esto.
- Añadir nodos: aumenta la capacidad física, y Kubernetes no lo hace por sí solo.

**4.3 ¿Qué sigue funcionando si falla…?**
- **Un Pod:** todo; el Deployment lo reemplaza.
- **Un worker:** la app sigue con las réplicas del otro worker. La base cuyo volumen estaba en ese worker queda fuera hasta que el nodo vuelva: si es MongoDB, la app sigue; si es PostgreSQL, no.
- **El control plane:** lo que ya corre sigue atendiendo, pero no hay reprogramación, HPA ni despliegues.
- **El almacenamiento:** se restaura desde el respaldo (RTO de 78 s).

**4.4 ¿Cómo se demuestra que una conexión la bloqueó la política y no un servicio caído?**
`networkpolicy.sh` usa controles:
- el mismo destino responde desde un Pod autorizado;
- el DNS funciona;
- el intento bloqueado termina en **timeout**, no en "connection refused".

---

## 5. Cambio en vivo: datos de prueba, respaldo y reversión (unos 2 min)

El profesor exige que un cambio en vivo use datos de prueba, tenga respaldo previo y un procedimiento de reversión. Esta receta cumple los tres:

```bash
# 1) Respaldo previo
$K create job respaldo-pre-cambio --from=cronjob/respaldo && $K wait --for=condition=complete job/respaldo-pre-cambio --timeout=120s
# 2) Dato de prueba: en la app de prod (Hogares > + Registrar hogar) crea el hogar PRUEBA-REV
# 3) Cambio: actualización gradual a 1.1.0 (compatible con el esquema actual)
$K set image deploy/backend backend=k3d-ra-registry.localhost:5050/redalimenta-backend@sha256:42225dac0603da29c8ce8cf3a010854e12b7caf0b1c208d292d65b76659f8fa5
$K rollout status deploy/backend
curl -s --cacert secrets/ca-prod.crt $PROD/api/version          # {"version":"1.1.0",...}
# 4) Reversión
$K rollout undo deploy/backend && $K rollout status deploy/backend
curl -s --cacert secrets/ca-prod.crt $PROD/api/version          # {"version":"1.1.2",...}
# 5) Verificación: PRUEBA-REV sigue en la app (el rollback de imagen no toca datos). Después dalo de baja.
```
Ensáyala una vez antes del turno.

Otros pedidos rápidos:

| Pedido | Comando | Para revertir |
|---|---|---|
| Escalar | `$K scale deploy/frontend --replicas=3` | `$K scale deploy/frontend --replicas=2` |
| Ver logs | `$K logs deploy/backend --tail=20` | — |
| Historial de despliegue | `$K rollout history deploy/backend` | — |
| Describir el HPA | `$K describe hpa backend` | — |
| Restaurar un respaldo | Ver sección 3.4 | Restaura en un namespace aislado |

---

## 6. Si algo falla durante el turno

| Síntoma | Solución |
|---|---|
| La app no carga, o falta el firewall tras un reinicio | `infra/scripts/preparar-revision.sh` |
| Grafana o Prometheus no abren | El mismo script reabre los port-forwards |
| El navegador marca el certificado como no válido | Es la CA del laboratorio. Importa `secrets/ca-prod.crt`, o explica que en producción real se usaría ACME |
| Un CronJob aparece `Failed` | `$K create job respaldo-manual --from=cronjob/respaldo`. Desde el 2026-11-03 los CronJobs reintentan hasta 5 veces |
| Grafana pide iniciar sesión | Usuario `admin`; la contraseña es `GRAFANA_ADMIN` en `secrets/prod.env` (consúltala sin mostrarla en pantalla) |
