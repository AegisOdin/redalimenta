import os
from playwright.sync_api import sync_playwright
BASE, PWD, OUT = os.environ["BASE"], os.environ["PWD_SEED"], "/out"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True).new_page()
    pg.goto(BASE + "/"); pg.fill("input[type=email]", "admin@redalimenta.test"); pg.fill("input[type=password]", PWD)
    pg.click("button:has-text('Entrar')"); pg.wait_for_selector("text=Salir")
    for f, n in ((os.environ["F1"], "06-rastreo-mongo"), (os.environ["F2"], "06b-rastreo-retiro-sanitario")):
        pg.goto(f"{BASE}/#/rastreo?folio={f}"); pg.reload(); pg.wait_for_selector("text=Línea de tiempo"); pg.wait_for_timeout(800)
        pg.screenshot(path=f"{OUT}/dev-{n}.png", full_page=True); print("captura", n)
    b.close()
