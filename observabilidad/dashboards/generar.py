#!/usr/bin/env python3
"""Genera el ConfigMap del panel de Grafana 'RedAlimenta - Operación' (detectado por el sidecar)."""
import json

P = []
def panel(t, exprs, x, y, w=8, h=7, unit="short", kind="timeseries", ds="prometheus"):
    targets = [{"expr": e, "legendFormat": l, "refId": chr(65 + i), "datasource": {"type": ds, "uid": "prometheus" if ds == "prometheus" else "loki"}}
               for i, (e, l) in enumerate(exprs)]
    P.append({"type": kind, "title": t, "gridPos": {"x": x, "y": y, "w": w, "h": h}, "targets": targets,
              "datasource": {"type": ds, "uid": "prometheus" if ds == "prometheus" else "loki"},
              "fieldConfig": {"defaults": {"unit": unit}, "overrides": []}, "options": {"legend": {"displayMode": "list"}}})

NS = 'namespace="redalimenta"'
P.append({"type": "row", "title": "Aplicación", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 1}})
panel("Solicitudes por segundo (por estado)", [('sum by (status) (rate(redalimenta_http_requests_total[1m]))', "{{status}}")], 0, 1, unit="reqps")
panel("Latencia p95 (s)", [('histogram_quantile(0.95, sum by (le) (rate(redalimenta_http_request_duration_seconds_bucket{route!="/metrics"}[1m])))', "p95"),
                           ('histogram_quantile(0.50, sum by (le) (rate(redalimenta_http_request_duration_seconds_bucket{route!="/metrics"}[1m])))', "p50")], 8, 1, unit="s")
panel("Tasa de errores 5xx", [('(sum(rate(redalimenta_http_requests_total{status=~"5.."}[1m])) or vector(0)) / clamp_min(sum(rate(redalimenta_http_requests_total[1m])),0.001)', "errores")], 16, 1, unit="percentunit")
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
panel("Pods no listos / reinicios", [(f'sum(kube_pod_status_ready{{{NS},condition="false"}})', "no listos"),
                                     (f'sum(increase(kube_pod_container_status_restarts_total{{{NS}}}[10m]))', "reinicios 10m")], 0, 38)
panel("Alertas activas", [('sum by (alertname) (ALERTS{alertstate="firing"})', "{{alertname}}")], 8, 38)
panel("Logs de la aplicación", [('{namespace="redalimenta", app=~"backend|outbox"}', "")], 16, 38, kind="logs", ds="loki", h=7)

dash = {"title": "RedAlimenta - Operación", "uid": "redalimenta-op", "timezone": "browser", "schemaVersion": 39,
        "refresh": "10s", "time": {"from": "now-30m", "to": "now"}, "panels": P, "tags": ["redalimenta"]}
cm = {"apiVersion": "v1", "kind": "ConfigMap",
      "metadata": {"name": "dashboard-redalimenta", "namespace": "monitoring", "labels": {"grafana_dashboard": "1"}},
      "data": {"redalimenta.json": json.dumps(dash, ensure_ascii=False)}}
open(__file__.replace("generar.py", "redalimenta-dashboard.yaml"), "w").write(json.dumps(cm, ensure_ascii=False, indent=1))
print("ok")
