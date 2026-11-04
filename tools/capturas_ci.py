from playwright.sync_api import sync_playwright
U = "https://github.com/AegisOdin/redalimenta/actions/runs/"
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width": 1500, "height": 950}, locale="es-MX").new_page()
    for run, name in [("41772759298", "ci-01-github-actions-exito"), ("41772601095", "ci-02-github-actions-fallo-ghcr")]:
        pg.goto(U + run); pg.wait_for_timeout(5000); pg.screenshot(path=f"/out/{name}.png"); print(name)
    b.close()
