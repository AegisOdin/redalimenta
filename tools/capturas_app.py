"""Capturas de la aplicación con Chromium headless (Playwright). Uso dentro del contenedor de Playwright.
Variables: BASE, PWD_SEED, PREFIJO, OUT."""
import os
from playwright.sync_api import sync_playwright

BASE, PWD, PRE, OUT = os.environ["BASE"], os.environ["PWD_SEED"], os.environ["PREFIJO"], os.environ.get("OUT", "/out")


def shot(page, nombre, full=False):
    page.wait_for_timeout(700)
    page.screenshot(path=f"{OUT}/{PRE}-{nombre}.png", full_page=full)
    print("captura", nombre)


def login(page, email):
    page.goto(BASE + "/")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", PWD)
    page.click("button:has-text('Entrar')")
    page.wait_for_selector("text=Salir")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=True, locale="es-MX")
    pg = ctx.new_page()
    pg.goto(BASE + "/"); pg.wait_for_selector("text=Entrar"); shot(pg, "01-login")
    # error de autenticación visible
    pg.fill("input[type=email]", "admin@redalimenta.test"); pg.fill("input[type=password]", "incorrecta"); pg.click("button:has-text('Entrar')")
    pg.wait_for_selector("text=Credenciales"); shot(pg, "02-login-error")
    login(pg, "admin@redalimenta.test"); shot(pg, "03-inicio-admin")
    pg.goto(BASE + "/#/lotes"); pg.wait_for_selector("table tbody tr"); shot(pg, "04-lotes-admin")
    pg.fill("input[placeholder^='Buscar folio']", "leche"); pg.wait_for_timeout(900); shot(pg, "05-lotes-busqueda")
    pg.goto(BASE + "/#/rastreo?folio=S-00001"); pg.reload(); pg.wait_for_selector("text=Línea de tiempo"); shot(pg, "06-rastreo-mongo", full=True)
    pg.goto(BASE + "/#/reportes"); pg.wait_for_selector("text=Kilos distribuidos"); shot(pg, "07-reportes", full=True)
    pg.goto(BASE + "/#/usuarios"); pg.wait_for_selector("table tbody tr"); shot(pg, "08-usuarios")
    pg.goto(BASE + "/#/catalogos"); pg.wait_for_selector("text=Productos"); shot(pg, "09-catalogos")
    pg.click("button:has-text('Salir')")
    # trabajador social: hogares, validación y solicitud
    login(pg, "social@redalimenta.test")
    pg.goto(BASE + "/#/hogares"); pg.wait_for_selector("table tbody tr"); shot(pg, "10-hogares-social")
    pg.click("button:has-text('+ Registrar hogar')"); pg.fill("input[placeholder='H-0200']", "x"); pg.click("form button:has-text('Guardar')")
    pg.wait_for_selector(".modal .alerta.error"); shot(pg, "11-validacion-cliente")
    pg.keyboard.press("Escape"); pg.goto(BASE + "/#/despensas"); pg.reload(); pg.wait_for_selector("table tbody tr")
    pg.click("table tbody tr >> nth=0"); pg.wait_for_selector(".modal"); shot(pg, "12-despensa-flujo")
    pg.goto(BASE + "/"); pg.click("button:has-text('Salir')")
    # coordinador: inspección con checklist por tipo de producto
    login(pg, "coordinador@redalimenta.test")
    pg.goto(BASE + "/#/lotes"); pg.reload(); pg.select_option("select", "recibido"); pg.wait_for_timeout(900)
    btn = pg.locator("button:has-text('Inspeccionar')").first
    if btn.count():
        btn.click(); pg.wait_for_selector(".modal"); shot(pg, "13-inspeccion-checklist")
    pg.goto(BASE + "/"); pg.click("button:has-text('Salir')")
    login(pg, "voluntario.norte@redalimenta.test"); shot(pg, "14-inicio-voluntario")
    # vista adaptable (móvil)
    m = b.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=True, is_mobile=True)
    mp = m.new_page(); mp.goto(BASE + "/"); mp.fill("input[type=email]", "coordinador@redalimenta.test"); mp.fill("input[type=password]", PWD)
    mp.click("button:has-text('Entrar')"); mp.wait_for_selector("text=Salir"); mp.goto(BASE + "/#/lotes"); mp.reload(); mp.wait_for_selector("table tbody tr")
    shot(mp, "15-movil-lotes")
    b.close()
