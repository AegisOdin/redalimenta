"""Pruebas funcionales contra la API publicada (dev o prod). Ejecutan reglas de negocio aunque se evite la UI."""
from datetime import date, timedelta

from conftest import Cliente, USERS, PWD

HOY = date.today()


def _producto(admin, uid, **kw):
    datos = {"nombre": f"Prueba {uid}", "categoria": "enlatado", "refrigerado": False, "alergenos": [],
             "peso_unitario_kg": "0.5", "unidades_por_racion": "0", **kw}
    r = admin.post("/api/productos", datos)
    assert r.status_code == 201, r.text
    return r.json()


def _donante(admin):
    return admin.get("/api/donantes").json()[0]


def _lote_disponible(coord, prod, don, cad, cant=10, temp=None):
    r = coord.post("/api/lotes", {"producto_id": prod["id"], "donante_id": don["id"], "cantidad_inicial": cant,
                                  "fecha_caducidad": str(cad)})
    assert r.status_code == 201, r.text
    l = r.json()
    r = coord.post(f"/api/lotes/{l['id']}/inspeccion", {"temperatura_c": temp, "checklist": {"prueba": True}})
    assert r.status_code == 200, r.text
    return r.json()


def _hogar(social, uid, **kw):
    datos = {"clave": f"T-{uid}", "responsable": "Hogar de prueba", "integrantes": 3, "alergenos": [],
             "colonia": "Col. Prueba", "ruta": "Norte", **kw}
    r = social.post("/api/hogares", datos)
    assert r.status_code == 201, r.text
    return r.json()


# ---------- autenticación y sesión
def test_login_invalido():
    c = Cliente()
    r = c.post("/api/auth/login", {"email": USERS["admin"], "password": "incorrecta"})
    assert r.status_code == 401 and "Credenciales" in r.json()["detail"]


def test_sin_sesion():
    assert Cliente().get("/api/lotes").status_code == 401


def test_token_manipulado():
    c = Cliente()
    c.c.cookies.set("ra_session", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.firma-falsa")
    assert c.get("/api/auth/me").status_code == 401


def test_csrf_obligatorio(coord):
    r = coord.post("/api/lotes", {"producto_id": 1, "donante_id": 1, "cantidad_inicial": 1,
                                  "fecha_caducidad": str(HOY + timedelta(days=30))}, csrf=False)
    assert r.status_code == 403 and "CSRF" in r.json()["detail"]


# ---------- autorización por rol (servidor)
def test_voluntario_no_registra_lotes(vol):
    r = vol.post("/api/lotes", {"producto_id": 1, "donante_id": 1, "cantidad_inicial": 5,
                                "fecha_caducidad": str(HOY + timedelta(days=30))})
    assert r.status_code == 403


def test_social_no_modifica_inventario(social):
    assert social.post("/api/lotes/1/inspeccion", {"temperatura_c": 3}).status_code == 403


def test_coordinador_no_da_alta_hogares(coord, uid):
    r = coord.post("/api/hogares", {"clave": f"X-{uid}", "responsable": "Nadie", "integrantes": 2,
                                    "colonia": "Col. C", "ruta": "Norte"})
    assert r.status_code == 403


def test_admin_no_confirma_entregas(admin):
    r = admin.post("/api/despensas/1/transicion/entregada", {})
    assert r.status_code in (403, 409)


def test_solo_admin_gestiona_usuarios(coord):
    assert coord.get("/api/usuarios").status_code == 403


def test_voluntario_solo_ve_su_ruta(vol):
    items = vol.get("/api/hogares?size=100").json()["items"]
    assert items and all(h["ruta"] == "Norte" for h in items)


# ---------- validaciones
def test_validacion_rangos(social, uid):
    r = social.post("/api/hogares", {"clave": f"V-{uid}", "responsable": "Hogar Ok", "integrantes": 0,
                                     "colonia": "Col. C", "ruta": "Norte"})
    assert r.status_code == 422 and r.json()["errores"][0]["campo"] == "integrantes"


def test_validacion_alergeno_desconocido(social, uid):
    r = social.post("/api/hogares", {"clave": f"V-{uid}", "responsable": "Hogar Ok", "integrantes": 2,
                                     "alergenos": ["kriptonita"], "colonia": "Col. C", "ruta": "Norte"})
    assert r.status_code == 422


def test_duplicado_clave_hogar(social, uid):
    _hogar(social, uid)
    r = social.post("/api/hogares", {"clave": f"T-{uid}", "responsable": "Otro", "integrantes": 2,
                                     "colonia": "Col. C", "ruta": "Norte"})
    assert r.status_code == 409


def test_lote_caducado_no_se_recibe(coord, admin):
    don = _donante(admin)
    r = coord.post("/api/lotes", {"producto_id": 1, "donante_id": don["id"], "cantidad_inicial": 5,
                                  "fecha_caducidad": str(HOY - timedelta(days=1))})
    assert r.status_code == 422


# ---------- CRUD de las tres entidades
def test_crud_lote(coord, admin, uid):
    prod, don = _producto(admin, uid), _donante(admin)
    r = coord.post("/api/lotes", {"producto_id": prod["id"], "donante_id": don["id"], "cantidad_inicial": 50,
                                  "fecha_caducidad": str(HOY + timedelta(days=60))})
    assert r.status_code == 201
    l = r.json()
    assert coord.get(f"/api/lotes/{l['id']}").json()["folio"] == l["folio"]
    r = coord.put(f"/api/lotes/{l['id']}", {"cantidad_inicial": 40})
    assert r.json()["cantidad_disponible"] == 40
    assert coord.get(f"/api/lotes?q={l['folio']}").json()["total"] == 1
    assert coord.delete(f"/api/lotes/{l['id']}").status_code == 204
    assert coord.get(f"/api/lotes/{l['id']}").status_code == 404


def test_crud_hogar(social, uid):
    h = _hogar(social, uid, integrantes=5)
    assert h["raciones"] == 3.0  # 1 + 0.5*4
    r = social.put(f"/api/hogares/{h['id']}", {**{k: h[k] for k in ("clave", "responsable", "colonia", "ruta",
                                                                     "alergenos")}, "integrantes": 9})
    assert r.json()["raciones"] == 4.0  # tope de 4 raciones
    assert social.delete(f"/api/hogares/{h['id']}").status_code == 204
    assert social.get(f"/api/hogares/{h['id']}").json()["activo"] is False


def test_paginacion_y_busqueda(coord):
    r = coord.get("/api/lotes?page=2&size=10").json()
    assert r["page"] == 2 and len(r["items"]) == 10 and r["total"] >= 100


# ---------- reglas de negocio y flujo
def test_cadena_de_frio(coord, admin, uid):
    prod = _producto(admin, uid, categoria="refrigerado", refrigerado=True)
    l = _lote_disponible(coord, prod, _donante(admin), HOY + timedelta(days=10), temp=7.5)
    assert l["estado"] == "rechazado" and "Cadena de frío" in l["motivo"]


def test_prioritario_por_caducidad(coord, admin, uid):
    l = _lote_disponible(coord, _producto(admin, uid), _donante(admin), HOY + timedelta(days=2))
    assert l["estado"] == "prioritario"


def test_flujo_completo_fefo_alergenos_y_14_dias(admin, coord, social, uid):
    don = _donante(admin)
    canasta = _producto(admin, uid, unidades_por_racion="1")
    viejo = _lote_disponible(coord, canasta, don, HOY + timedelta(days=20), cant=50)
    nuevo = _lote_disponible(coord, canasta, don, HOY + timedelta(days=90), cant=50)
    alerg = _producto(admin, uid + "G", unidades_por_racion="1", alergenos=["gluten"])
    _lote_disponible(coord, alerg, don, HOY + timedelta(days=30), cant=50)
    h = _hogar(social, uid, alergenos=["gluten"])

    r = social.post("/api/despensas", {"hogar_id": h["id"], "fecha_programada": str(HOY + timedelta(days=1))})
    assert r.status_code == 201
    d = r.json()
    # no puede haber dos despensas abiertas
    assert social.post("/api/despensas", {"hogar_id": h["id"], "fecha_programada": str(HOY)}).status_code == 409
    # transición inválida (salto) y rol incorrecto
    assert coord.post(f"/api/despensas/{d['id']}/transicion/lista").status_code == 409
    assert coord.post(f"/api/despensas/{d['id']}/transicion/aprobada").status_code == 403
    assert social.post(f"/api/despensas/{d['id']}/transicion/aprobada").status_code == 200
    r = coord.post(f"/api/despensas/{d['id']}/transicion/en_preparacion")
    assert r.status_code == 200, r.text
    det = r.json()["despensa"]["detalle"]
    folios = [x["folio_lote"] for x in det]
    assert viejo["folio"] in folios and nuevo["folio"] not in folios      # FEFO automático
    assert any(o["producto"] == alerg["nombre"] for o in r.json()["omitidos_por_alergeno"])  # alérgeno
    # FEFO manual: elegir el lote nuevo existiendo uno anterior => 409
    r = coord.post(f"/api/despensas/{d['id']}/items", {"lote_id": nuevo["id"], "cantidad": 1})
    assert r.status_code == 409 and "FEFO" in r.json()["detail"]
    assert coord.post(f"/api/despensas/{d['id']}/transicion/lista").status_code == 200
    # voluntario de otra ruta no la ve
    otro = Cliente("voluntario.sur@redalimenta.test")
    assert otro.post(f"/api/despensas/{d['id']}/transicion/entregada").status_code == 404
    vol = Cliente(USERS["voluntario"])
    assert vol.post(f"/api/despensas/{d['id']}/transicion/entregada").status_code == 200
    # regla de 14 días: nueva solicitud se puede registrar pero no aprobar
    d2 = social.post("/api/despensas", {"hogar_id": h["id"], "fecha_programada": str(HOY + timedelta(days=2))}).json()
    r = social.post(f"/api/despensas/{d2['id']}/transicion/aprobada")
    assert r.status_code == 409 and "elegible" in r.json()["detail"]
    assert social.post(f"/api/despensas/{d2['id']}/transicion/rechazada").status_code == 200

    # retiro sanitario: lista el hogar que ya recibió el lote viejo
    r = admin.post(f"/api/lotes/{viejo['id']}/retiro-sanitario", {"motivo": "Prueba de retiro sanitario"})
    assert r.status_code == 200
    assert h["clave"] in [x["clave"] for x in r.json()["hogares_a_avisar"]]
    assert coord.post(f"/api/lotes/{viejo['id']}/retiro-sanitario", {"motivo": "otra vez"}).status_code == 403


def test_reporte_mensual(admin):
    r = admin.get("/api/reportes/mensual").json()
    assert "kilos_distribuidos" in r and "merma_por_categoria" in r and r["hogares_atendidos"] >= 0


def test_trazabilidad_mongo(coord):
    r = coord.get("/api/trazabilidad/lotes/S-00001")
    assert r.status_code == 200 and r.json()["expediente"]["folio_lote"] == "S-00001"
    assert coord.get("/api/trazabilidad/bitacora?tipo=lote_entregado").json()["total"] > 0


def test_sesion_expirada():
    """Requiere EXPIRED_TOKEN (firmado dentro del clúster por tests/seguridad/sesion-expirada.sh); si no, se omite."""
    import os, pytest
    tok = os.environ.get("EXPIRED_TOKEN")
    if not tok:
        pytest.skip("sin EXPIRED_TOKEN")
    c = Cliente()
    c.c.cookies.set("ra_session", tok)
    r = c.get("/api/auth/me")
    assert r.status_code == 401 and r.json()["detail"] == "Sesión expirada"
