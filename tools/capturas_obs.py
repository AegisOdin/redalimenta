"""Capturas de Grafana, Prometheus y Alertmanager (port-forward en localhost). Variables: GPASS, PREFIJO, DESDE (min)."""
import os
from playwright.sync_api import sync_playwright
PRE, DESDE = os.environ.get("PREFIJO", "obs"), os.environ.get("DESDE", "45")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1600, "height": 1850}).new_page()
    pg.goto("http://localhost:3000/login"); pg.fill("input[name=user]", "admin"); pg.fill("input[name=password]", os.environ["GPASS"])
    pg.click("button[type=submit]"); pg.wait_for_timeout(2500)
    pg.goto(f"http://localhost:3000/d/redalimenta-op?orgId=1&from=now-{DESDE}m&to=now&kiosk"); pg.wait_for_timeout(15000); pg.mouse.wheel(0, 2000); pg.wait_for_timeout(3000); pg.mouse.wheel(0, -2000); pg.wait_for_timeout(4000)
    pg.screenshot(path=f"/out/{PRE}-grafana-panel.png"); print("grafana")
    for uid, n in (("efhmr", "x"),):
        pass
    pg.goto("http://localhost:9090/alerts?search=redalimenta"); pg.wait_for_timeout(3000); pg.screenshot(path=f"/out/{PRE}-prometheus-alertas.png", full_page=False); print("prom alerts")
    pg.goto("http://localhost:9090/targets"); pg.wait_for_timeout(3000); pg.screenshot(path=f"/out/{PRE}-prometheus-targets.png"); print("targets")
    pg.goto("http://localhost:9093/#/alerts"); pg.wait_for_timeout(3000); pg.screenshot(path=f"/out/{PRE}-alertmanager.png"); print("am")
    pg.goto(f"http://localhost:3000/explore?orgId=1&schemaVersion=1&panes=%7B%22a%22:%7B%22datasource%22:%22loki%22,%22queries%22:%5B%7B%22refId%22:%22A%22,%22expr%22:%22%7Bnamespace%3D%5C%22redalimenta%5C%22,app%3D%5C%22backend%5C%22%7D%22,%22datasource%22:%7B%22type%22:%22loki%22,%22uid%22:%22loki%22%7D%7D%5D,%22range%22:%7B%22from%22:%22now-15m%22,%22to%22:%22now%22%7D%7D%7D")
    pg.wait_for_timeout(7000); pg.screenshot(path=f"/out/{PRE}-loki-logs.png"); print("loki")
    b.close()
