"""Semilla reproducible (random.Random(2026)) con datos 100% sintéticos.
Idempotente: si ya existe el marcador de semilla no hace nada. Fechas relativas a la fecha de ejecución."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
import random

from sqlalchemy import select, func, text

from . import events, rules
from .db import SessionLocal
from .models import Usuario, Donante, Producto, Lote, Hogar, Despensa, DespensaDetalle
from .security import hash_password

R = random.Random(2026)
RUTAS = ["Norte", "Sur", "Centro", "Oriente"]
NOMBRES = ["Ana", "Luis", "María", "José", "Carmen", "Jorge", "Lucía", "Pedro", "Rosa", "Miguel", "Elena",
           "Raúl", "Sofía", "Andrés", "Paula", "Diego", "Teresa", "Hugo", "Irene", "Óscar"]
APELLIDOS = ["Prueba", "Ficticio", "Demo", "Ejemplo", "Sintético", "Muestra", "Ensayo", "Modelo"]
COLONIAS = ["Col. Alfa", "Col. Beta", "Col. Gamma", "Col. Delta", "Col. Épsilon", "Col. Zeta", "Col. Eta"]
DONANTES = [("Supermercado Uno", "supermercado"), ("Supermercado Dos", "supermercado"),
            ("Tienda La Esquina", "supermercado"), ("Mercado Central Demo", "supermercado"),
            ("Huerta San Isidro", "productor"), ("Granja El Roble", "productor"), ("Lácteos del Valle", "productor"),
            ("Panadería Aurora", "productor"), ("Cooperativa Maíz", "productor"),
            ("Donante Particular A", "particular"), ("Donante Particular B", "particular"),
            ("Parroquia Vecinal", "particular")]
# nombre, categoria, refrigerado, alergenos, peso_kg, unidades_por_racion
PRODUCTOS = [("Leche entera 1 L", "refrigerado", True, ["lacteos"], "1.03", "2"),
             ("Yogur natural 1 kg", "refrigerado", True, ["lacteos"], "1", "0"),
             ("Queso fresco 400 g", "refrigerado", True, ["lacteos"], "0.4", "0"),
             ("Huevo 12 piezas", "refrigerado", True, ["huevo"], "0.72", "1"),
             ("Pollo entero", "refrigerado", True, [], "1.8", "0"),
             ("Atún en lata", "enlatado", False, ["mariscos"], "0.14", "2"),
             ("Frijol en lata", "enlatado", False, [], "0.56", "1"),
             ("Elote en lata", "enlatado", False, [], "0.4", "0"),
             ("Sardina en lata", "enlatado", False, ["mariscos"], "0.42", "0"),
             ("Manzana kg", "fruta_verdura", False, [], "1", "1"),
             ("Plátano kg", "fruta_verdura", False, [], "1", "1"),
             ("Jitomate kg", "fruta_verdura", False, [], "1", "0"),
             ("Papa kg", "fruta_verdura", False, [], "1", "1"),
             ("Arroz 1 kg", "granos", False, [], "1", "1"),
             ("Frijol negro 1 kg", "granos", False, [], "1", "1"),
             ("Avena 500 g", "granos", False, ["gluten"], "0.5", "0"),
             ("Pasta 200 g", "granos", False, ["gluten"], "0.2", "2"),
             ("Crema de cacahuate", "otros", False, ["cacahuate"], "0.34", "0"),
             ("Pan de caja", "panaderia", False, ["gluten", "soya"], "0.68", "1"),
             ("Tortilla de maíz kg", "panaderia", False, [], "1", "0")]


def checklist(cat: str):
    if cat == "refrigerado":
        lect = [round(R.uniform(1.5, 6.5), 1) for _ in range(3)]
        return {"lecturas_temp": lect, "empaque_integro": R.random() > 0.05, "transporte_refrigerado": True}, max(lect)
    if cat == "enlatado":
        return {"lote_fabricante": f"FAB-{R.randint(1000, 9999)}", "estado_lata": R.choice(
            ["sin_abolladuras", "sin_abolladuras", "abolladura_leve"]), "etiqueta_legible": True}, None
    if cat == "fruta_verdura":
        return {"grado_madurez": R.choice(["verde", "pinton", "maduro"]), "porcentaje_danado": R.randint(0, 15)}, None
    if cat == "granos":
        return {"humedad_visible": False, "plagas": False, "empaque": R.choice(["costal", "bolsa"])}, None
    if cat == "panaderia":
        return {"horas_desde_horneado": R.randint(2, 30), "moho": False}, None
    return {"sello_intacto": True}, None


def ts(d: date, h=10) -> str:
    return datetime(d.year, d.month, d.day, h, R.randint(0, 59), tzinfo=timezone.utc).isoformat()


def main():
    pwd = os.environ["SEED_PASSWORD"]  # llega desde un Secret; nunca se versiona
    hoy = date.today()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Lote).where(Lote.folio.like("S-%"))):
            print("Semilla ya aplicada; no se hace nada (idempotente)")
            return
        usuarios = [("admin@redalimenta.test", "Admin Demo", "admin", None),
                    ("coordinador@redalimenta.test", "Coordinador Demo", "coordinador", None),
                    ("coordinador2@redalimenta.test", "Coordinadora Dos", "coordinador", None),
                    ("social@redalimenta.test", "Trabajadora Social Demo", "trabajador_social", None),
                    ("social2@redalimenta.test", "Trabajador Social Dos", "trabajador_social", None)]
        usuarios += [(f"voluntario.{r.lower()}@redalimenta.test", f"Voluntario {r}", "voluntario", r) for r in RUTAS]
        h = hash_password(pwd)
        U = {}
        for email, nombre, rol, ruta in usuarios:
            u = db.scalar(select(Usuario).where(Usuario.email == email))
            if not u:
                u = Usuario(email=email, nombre=nombre, rol=rol, ruta=ruta, password_hash=h)
                db.add(u)
            U[email] = u
        db.flush()
        coord, social = U["coordinador@redalimenta.test"], U["social@redalimenta.test"]
        D = []
        for n, t in DONANTES:
            d = db.scalar(select(Donante).where(Donante.nombre == n)) or Donante(nombre=n, tipo=t, contacto="contacto@ejemplo.test")
            db.add(d)
            D.append(d)
        P = []
        for n, c, refr, al, peso, upr in PRODUCTOS:
            p = db.scalar(select(Producto).where(Producto.nombre == n)) or Producto(
                nombre=n, categoria=c, refrigerado=refr, alergenos=al, peso_unitario_kg=Decimal(peso),
                unidades_por_racion=Decimal(upr))
            db.add(p)
            P.append(p)
        db.flush()

        # --- 160 lotes
        lotes = []
        for i in range(1, 161):
            p, d = R.choice(P), R.choice(D)
            rec = hoy - timedelta(days=R.randint(0, 45))
            r = R.random()
            cad = (hoy - timedelta(days=R.randint(1, 10))) if r < 0.08 else \
                  (hoy + timedelta(days=R.randint(0, 3))) if r < 0.2 else hoy + timedelta(days=R.randint(5, 120))
            cad = max(cad, rec)
            cant = R.randint(20, 200)
            l = Lote(folio=f"S-{i:05d}", producto_id=p.id, donante_id=d.id, cantidad_inicial=cant,
                     cantidad_disponible=cant, fecha_recepcion=rec, fecha_caducidad=cad, estado="recibido",
                     creado_por=coord.id)
            db.add(l)
            db.flush()
            events.registrar(db, "lote_recibido", l.id, coord.id, ts=ts(rec, 9), folio_lote=l.folio, producto=p.nombre,
                             categoria=p.categoria, refrigerado=p.refrigerado, alergenos=p.alergenos, donante=d.nombre,
                             donante_tipo=d.tipo, cantidad=cant, fecha_caducidad=str(cad))
            if i > 150:   # 10 lotes quedan pendientes de inspección para la demostración
                lotes.append((l, p))
                continue
            chk, temp = checklist(p.categoria)
            estado, motivo = rules.resultado_inspeccion(p, temp, True)
            if estado == "disponible":
                estado = rules.estado_por_caducidad(cad)
            l.estado, l.temperatura_c, l.motivo = estado, (Decimal(str(temp)) if temp is not None else None), motivo
            if estado == "rechazado":
                l.cantidad_disponible = 0
            events.registrar(db, "lote_inspeccionado", l.id, coord.id, ts=ts(rec, 11), folio_lote=l.folio,
                             resultado=estado, motivo=motivo, temperatura_c=temp, checklist=chk, categoria=p.categoria)
            lotes.append((l, p))

        # --- 120 hogares
        hogares = []
        for i in range(1, 121):
            al = R.sample(["gluten", "lacteos", "cacahuate", "huevo", "mariscos"], k=1) if R.random() < 0.2 else []
            hg = Hogar(clave=f"H-{i:04d}", responsable=f"{R.choice(NOMBRES)} {R.choice(APELLIDOS)}",
                       integrantes=R.randint(1, 8), alergenos=al, colonia=R.choice(COLONIAS), ruta=R.choice(RUTAS),
                       telefono=f"555 000 {i:04d}")
            db.add(hg)
            hogares.append(hg)
        db.flush()

        # --- 70 despensas entregadas (historial) usando lotes asignables reales, respetando alérgenos
        seq = 0
        asignables = [(l, p) for l, p in lotes if l.estado in ("disponible", "prioritario", "merma")
                      and l.cantidad_disponible > 10]
        for hg in R.sample(hogares, 70):
            seq += 1
            f_ent = hoy - timedelta(days=R.randint(1, 60))
            d = Despensa(folio=f"S-D-{seq:05d}", hogar_id=hg.id, estado="entregada", raciones=rules.raciones(hg.integrantes),
                         fecha_programada=f_ent, solicitada_por=social.id, aprobada_por=social.id, preparada_por=coord.id,
                         entregada_por=U[f"voluntario.{hg.ruta.lower()}@redalimenta.test"].id,
                         entregada_en=datetime(f_ent.year, f_ent.month, f_ent.day, 15, tzinfo=timezone.utc),
                         lista_en=datetime(f_ent.year, f_ent.month, f_ent.day, 9, tzinfo=timezone.utc))
            db.add(d)
            db.flush()
            for l, p in R.sample(asignables, 3):
                if set(p.alergenos) & set(hg.alergenos) or l.cantidad_disponible < 5:
                    continue
                c = R.randint(1, 4)
                l.cantidad_disponible -= c
                db.add(DespensaDetalle(despensa_id=d.id, lote_id=l.id, cantidad=c))
                events.registrar(db, "lote_asignado", l.id, coord.id, ts=ts(f_ent, 8), folio_lote=l.folio,
                                 despensa=d.folio, hogar_id=hg.id, cantidad=c)
                events.registrar(db, "lote_entregado", l.id, d.entregada_por, ts=ts(f_ent, 15), folio_lote=l.folio,
                                 despensa=d.folio, hogar_id=hg.id, hogar_clave=hg.clave, cantidad=c)
            events.registrar(db, "despensa_entregada", None, d.entregada_por, ts=ts(f_ent, 15), despensa=d.folio,
                             hogar_id=hg.id)
            hg.ultima_entrega = max(hg.ultima_entrega or f_ent, f_ent)

        # --- 15 solicitudes abiertas de hogares elegibles
        elegibles = [hg for hg in hogares if rules.elegible(hg, hoy)[0]]
        for hg in R.sample(elegibles, 15):
            seq += 1
            db.add(Despensa(folio=f"S-D-{seq:05d}", hogar_id=hg.id, estado="solicitada",
                            raciones=rules.raciones(hg.integrantes), fecha_programada=hoy + timedelta(days=R.randint(1, 5)),
                            solicitada_por=social.id))
        db.commit()
        db.execute(text("SELECT setval('folio_lote_seq', 1000, false)"))
        db.commit()
        tot = {t: db.scalar(text(f"SELECT count(*) FROM {t}")) for t in
               ("usuarios", "donantes", "productos", "lotes", "hogares", "despensas", "despensa_detalle", "outbox")}
        print("Semilla aplicada:", tot)


if __name__ == "__main__":
    main()
