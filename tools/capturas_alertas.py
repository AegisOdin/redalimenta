import os
from playwright.sync_api import sync_playwright
PRE = os.environ["PREFIJO"]
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1500, "height": 950}).new_page()
    pg.goto("http://localhost:9093/#/alerts?silenced=false&inhibited=false&filter=%7Bseverity%3D~%22critical%7Cwarning%22%7D"); pg.wait_for_timeout(4000)
    try: pg.click("text=Expand all groups", timeout=1500)
    except Exception: pass
    pg.wait_for_timeout(800); pg.screenshot(path=f"/out/{PRE}-alertmanager.png", full_page=True); print("am")
    pg.goto("http://localhost:9090/alerts?search=redalimenta"); pg.wait_for_timeout(3000)
    pg.screenshot(path=f"/out/{PRE}-prometheus-alertas.png", full_page=True); print("prom")
    b.close()
