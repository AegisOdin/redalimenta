#!/usr/bin/env python3
"""Genera el ConfigMap del panel de Grafana 'RedAlimenta - Operación' (detectado por el sidecar)."""
import json

P = []
def panel(t, exprs, x, y, w=8, h=7, unit="short", kind="timeseries", ds="prometheus", vmin=None, vmax=None, umbrales=None):
    targets = [{"expr": e, "legendFormat": l, "refId": chr(65 + i), "datasource": {"type": ds, "uid": "prometheus" if ds == "prometheus" else "loki"}}
               for i, (e, l) in enumerate(exprs)]
    P.append({"type": kind, "title": t, "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
              "datasource": {"type": ds, "uid": "prometheus" if ds == "prometheus" else "loki"},
              "fieldConfig": {"defaults": {"unit": unit, **({"min": vmin} if vmin is not None else {}), **({"max": vmax} if vmax is not None else {}),
                                           **({"thresholds": {"mode": "absolute", "steps": umbrales}} if umbrales else {})}, "overrides": []}, "options": {"legend": {"displayMode": "list"}}})

NS = 'namespace="redalimenta"'
P.append({"type": "row", "title": "Aplicación", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 1}})
panel("Solicitudes por segundo (por estado)", [('sum by (status) (rate(redalimenta_http_requests_total[1m]))', "{{status}}")], 0, 1, unit="reqps")
panel("Latencia p95 (s)", [('histogram_quantile(0.95, sum by (le) (rate(redalimenta_http_request_duration_seconds_bucket{route!="/metrics"}[1m])))', "p95"),
                           ('histogram_quantile(0.50, sum by (le) (rate(redalimenta_http_request_duration_seconds_bucket{route!="/metrics"}[1m])))', "p50")], 8, 1, unit="s")
panel("Tasa de errores 5xx", [('(sum(rate(redalimenta_http_requests_total{status=~"5.."}[1m])) or vector(0)) / clamp_min(sum(rate(redalimenta_http_requests_total[1m])),0.001)', "errores")], 16, 1, unit="percentunit", vmin=0, vmax=1)
panel("Réplicas backend (HPA)", [(f'kube_horizontalpodautoscaler_status_desired_replicas{{{NS}}}', "deseadas"),
                                 (f'kube_horizontalpodautoscaler_status_current_replicas{{{NS}}}', "actuales"),
                                 (f'kube_deployment_status_replicas_ready{{{NS},deployment="backend"}}', "Ready")], 0, 8)
panel("CPU por Pod (cores)", [(f'sum by (pod) (rate(container_cpu_usage_seconds_total{{{NS},container!=""}}[1m]))', "{{pod}}")], 8, 8)
panel("Memoria por Pod", [(f'sum by (pod) (container_memory_working_set_bytes{{{NS},container!=""}})', "{{pod}}")], 16, 8, unit="bytes")
P.append({"type": "row", "title": "Bases de datos", "gridPos": {"x": 0, "y": 15, "w": 24, "h": 1}})
panel("Disponibilidad", [("pg_up", "PostgreSQL"), ("mongodb_up", "MongoDB"), ('max by (dependency) (redalimenta_dependency_up)', "app→{{dependency}}")], 0, 16, w=6)
panel("Conexiones PostgreSQL", [('sum by (state) (pg_stat_activity_count{datname="redalimenta"})', "{{state}}")], 6, 16, w=6)
panel("Transacciones PostgreSQL /s", [('rate(pg_stat_database_xact_commit{datname="redalimenta"}[1m])', "commit"),
                                       ('rate(pg_stat_database_xact_rollback{datname="redalimenta"}[1m])', "rollback")], 12, 16, w=6)
panel("Tamaño BD", [('pg_database_size_bytes{datname="redalimenta"}', "PostgreSQL"), ('sum(mongodb_dbstats_dataSize{database="redalimenta"})', "MongoDB")], 18, 16, w=6, unit="bytes")
panel("Conexiones MongoDB", [('mongodb_ss_connections{conn_type="current"}', "actuales")], 0, 23, w=6)
panel("Operaciones MongoDB /s", [('sum by (legacy_op_type) (rate(mongodb_ss_opcounters[1m]))', "{{legacy_op_type}}")], 6, 23, w=6)
panel("Latencia MongoDB (µs/op)", [('rate(mongodb_ss_opLatencies_latency[1m]) / clamp_min(rate(mongodb_ss_opLatencies_ops[1m]),1)', "{{op_type}}")], 12, 23, w=6, unit="µs")
panel("Outbox pendiente", [("max(redalimenta_outbox_pendientes)", "pendientes"), ("sum(rate(redalimenta_outbox_publicados_total[1m]))", "publicados/s")], 18, 23, w=6)
P.append({"type": "row", "title": "Infraestructura y respaldos", "gridPos": {"x": 0, "y": 30, "w": 24, "h": 1}})
panel("CPU por nodo", [('1 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[1m]))', "{{instance}}")], 0, 31, unit="percentunit")
panel("Memoria de Pods / asignable por nodo", [('sum by (node) (container_memory_working_set_bytes{container!="",pod!=""}) / on (node) group_left kube_node_status_allocatable{resource="memory"}', "{{node}}")], 8, 31, unit="percentunit")
panel("Antigüedad del último respaldo válido (h)", [('(time() - max(kube_cronjob_status_last_successful_time{namespace="redalimenta",cronjob="respaldo"})) / 3600', "horas")], 16, 31, unit="h", kind="stat")
panel("Pods no listos / reinicios", [(f'sum((kube_pod_status_ready{{{NS},condition="false"}} == 1) and on(namespace, pod) (kube_pod_status_phase{{{NS},phase=~"Running|Pending"}} == 1)) or vector(0)', "no listos (excluye Jobs terminados)"),
                                     (f'sum(increase(kube_pod_container_status_restarts_total{{{NS}}}[10m]))', "reinicios 10m")], 0, 38)
panel("Alertas activas", [('sum by (alertname) (ALERTS{alertstate="firing"})', "{{alertname}}")], 8, 38)
panel("Logs de la aplicación", [('{namespace="redalimenta", app=~"backend|outbox"} != "/readyz" != "/healthz" != "/metrics"', "")], 16, 38, kind="logs", ds="loki", h=7)

# --- Cobertura de la sección 10 de la práctica: nodos (disco/red), Kubernetes, entrada y seguridad, PostgreSQL y respaldos
P.append({"type": "row", "title": "Nodos y Kubernetes", "gridPos": {"x": 0, "y": 45, "w": 24, "h": 1}})
panel("Nodos Ready", [('sum(kube_node_status_condition{condition="Ready",status="true"})', "Ready"),
                      ('count(kube_node_info)', "total")], 0, 46, w=4, kind="stat")
panel("Disco usado (volumen de k3s, compartido con el host)", [('max by (instance) (1 - node_filesystem_avail_bytes{mountpoint="/var/lib/rancher/k3s"} / node_filesystem_size_bytes{mountpoint="/var/lib/rancher/k3s"})', "{{instance}}")], 4, 46, w=7, unit="percentunit", vmin=0, vmax=1)
panel("Red por nodo (eth0)", [('rate(node_network_receive_bytes_total{device="eth0"}[1m])', "rx {{instance}}"),
                              ('-rate(node_network_transmit_bytes_total{device="eth0"}[1m])', "tx {{instance}}")], 11, 46, w=7, unit="Bps")
panel("Pods Pending (redalimenta)", [(f'sum(kube_pod_status_phase{{{NS},phase="Pending"}})', "Pending")], 18, 46, w=6)
panel("Réplicas deseadas vs disponibles", [(f'kube_deployment_spec_replicas{{{NS}}}', "deseadas {{deployment}}"),
                                            (f'kube_deployment_status_replicas_available{{{NS}}}', "disponibles {{deployment}}")], 0, 53, w=10)
panel("Eventos de Kubernetes (redalimenta)", [('{job="eventos-kubernetes"}', "")], 10, 53, w=14, kind="logs", ds="loki")
P.append({"type": "row", "title": "Entrada, TLS y seguridad", "gridPos": {"x": 0, "y": 60, "w": 24, "h": 1}})
panel("Traefik: solicitudes/s por entrypoint y código", [('sum by (entrypoint, code) (rate(traefik_entrypoint_requests_total[1m]))', "{{entrypoint}} {{code}}")], 0, 61, w=9, unit="reqps")
panel("Traefik: réplicas de la entrada arriba", [('sum(up{job="traefik/traefik"})', "réplicas up")], 9, 61, w=4, kind="stat")
panel("Días para expirar cada certificado TLS", [('min by (name) (certmanager_certificate_expiration_timestamp_seconds - time()) / 86400', "{{name}}")], 13, 61, w=5, kind="stat", unit="none",
      umbrales=[{"color": "red", "value": None}, {"color": "yellow", "value": 7}, {"color": "green", "value": 30}])
panel("Rechazos observables (401 / 403 / 429)", [('sum by (status) (rate(redalimenta_http_requests_total{status=~"401|403|429"}[5m]))', "{{status}}")], 18, 61, w=6, unit="reqps")
P.append({"type": "row", "title": "PostgreSQL (detalle) y respaldos", "gridPos": {"x": 0, "y": 68, "w": 24, "h": 1}})
panel("PostgreSQL: duración máxima de transacción", [('max by (state) (pg_stat_activity_max_tx_duration{datname="redalimenta"})', "{{state}}")], 0, 69, w=5, unit="s")
panel("PostgreSQL: conexiones / máximo", [('sum(pg_stat_database_numbackends{datname="redalimenta"})', "en uso"), ('max(pg_settings_max_connections)', "max_connections")], 5, 69, w=5)
panel("Respaldos: Jobs exitosos / fallidos", [(f'sum(kube_job_status_succeeded{{{NS},job_name=~"respaldo.*"}})', "exitosos"),
                                             (f'sum(kube_job_status_failed{{{NS},job_name=~"respaldo.*"}}) or vector(0)', "fallidos")], 10, 69, w=3, kind="stat")
panel("Respaldos: horas desde la última ejecución", [(f'(time() - max(kube_cronjob_status_last_schedule_time{{{NS},cronjob="respaldo"}})) / 3600', "horas")], 13, 69, w=3, kind="stat", unit="h")
panel("Respaldos: tamaño por motor", [('max by (motor) (max_over_time({namespace="redalimenta", app="respaldo"} |= "motor" | json | unwrap bytes [26h]))', "{{motor}}")], 16, 69, w=4, ds="loki", unit="bytes")
panel("Respaldos: duración por motor (s)", [('max by (motor) (max_over_time({namespace="redalimenta", app="respaldo"} |= "motor" | json | unwrap segundos [26h]))', "{{motor}}")], 20, 69, w=4, ds="loki", unit="s")

dash = {"title": "RedAlimenta - Operación", "uid": "redalimenta-op", "timezone": "browser", "schemaVersion": 39,
        "refresh": "10s", "time": {"from": "now-30m", "to": "now"}, "panels": P, "tags": ["redalimenta"]}
cm = {"apiVersion": "v1", "kind": "ConfigMap",
      "metadata": {"name": "dashboard-redalimenta", "namespace": "monitoring", "labels": {"grafana_dashboard": "1"}},
      "data": {"redalimenta.json": json.dumps(dash, ensure_ascii=False)}}
open(__file__.replace("generar.py", "redalimenta-dashboard.yaml"), "w").write(json.dumps(cm, ensure_ascii=False, indent=1))
print("ok")
