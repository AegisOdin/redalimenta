"""Verifica en la UI que el administrador ve las acciones de todos los roles (versión 1.1.2) y toma capturas.
Variables: BASE, PWD_SEED, OUT."""
import os
from playwright.sync_api import sync_playwright

BASE, PWD, OUT = os.environ["BASE"], os.environ["PWD_SEED"], os.environ.get("OUT", "/out")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True, locale="es-MX").new_page()
    pg.goto(BASE + "/"); pg.fill("input[type=email]", "admin@redalimenta.test"); pg.fill("input[type=password]", PWD)
    pg.click("button:has-text('Entrar')"); pg.wait_for_selector("text=Salir")
    menu = [t.strip() for t in pg.locator("nav a, nav button").all_inner_texts()]
    print("menú:", menu)
    pg.goto(BASE + "/#/lotes"); pg.wait_for_timeout(1500)
    print("Lotes  · '+ Recibir donativo':", pg.locator("button:has-text('Recibir donativo')").count(),
          "· 'Inspeccionar':", pg.locator("button:has-text('Inspeccionar')").count(),
          "· 'Retiro sanitario':", pg.locator("button:has-text('Retiro sanitario')").count())
    pg.screenshot(path=f"{OUT}/dev-16-admin-lotes.png")
    pg.goto(BASE + "/#/hogares"); pg.wait_for_timeout(1500)
    print("Hogares · '+ Registrar hogar':", pg.locator("button:has-text('Registrar hogar')").count())
    pg.screenshot(path=f"{OUT}/dev-17-admin-hogares.png")
    b.close()
