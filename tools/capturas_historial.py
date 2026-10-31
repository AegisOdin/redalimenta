import urllib.parse
from playwright.sync_api import sync_playwright
q = 'max by (alertname) (ALERTS{alertstate="firing", alertname=~"OutboxAtrasado|BaseDeDatosCaida|AplicacionIndisponible|TasaDeErroresElevada|RespaldoFallido|SaturacionDeRecursos"})'
url = "http://localhost:9090/query?g0.expr=" + urllib.parse.quote(q) + "&g0.show_tree=0&g0.tab=graph&g0.range_input=1h30m&g0.res_type=auto&g0.display_mode=lines"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1500, "height": 900}).new_page()
    pg.goto(url); pg.wait_for_timeout(6000); pg.screenshot(path="/out/E10-historial-alertas-prometheus.png"); print("ok")
    b.close()
