"""Reglas de negocio de RedAlimenta (sección 4 de la propuesta).
Todas se aplican en el servidor; la interfaz solo las anticipa."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import math

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from . import events
from .models import Lote, Producto, Hogar, Despensa, DespensaDetalle, Usuario

DIAS_ENTRE_DESPENSAS = 14
DIAS_PRIORITARIO = 3
HORAS_PRIORIDAD_ENTREGA = 48
TEMP_MAX_REFRIGERADO = Decimal("5")
HORAS_NO_RECOGIDA = 72
ESTADOS_ASIGNABLES = ("disponible", "prioritario")
ESTADOS_DESPENSA_ABIERTA = ("solicitada", "aprobada", "en_preparacion", "lista")

# Transiciones válidas de la despensa: (origen, destino) -> roles autorizados (además, el administrador puede todas)
TRANSICIONES = {
    ("solicitada", "aprobada"): {"trabajador_social"},
    ("solicitada", "rechazada"): {"trabajador_social"},
    ("aprobada", "en_preparacion"): {"coordinador"},
    ("aprobada", "cancelada"): {"trabajador_social", "admin"},
    ("en_preparacion", "lista"): {"coordinador"},
    ("en_preparacion", "cancelada"): {"admin"},
    ("lista", "entregada"): {"voluntario"},
    ("lista", "no_recogida"): {"coordinador"},
}


def hoy() -> date:
    return date.today()


# Regla 3: frecuencia y tamaño por hogar
def raciones(integrantes: int) -> Decimal:
    r = Decimal(1) + Decimal("0.5") * (integrantes - 1)
    return min(r, Decimal(4))


def elegible(h: Hogar, fecha: date) -> tuple[bool, str]:
    if not h.activo:
        return False, "El hogar está inactivo"
    if h.ultima_entrega and (fecha - h.ultima_entrega).days < DIAS_ENTRE_DESPENSAS:
        prox = h.ultima_entrega + timedelta(days=DIAS_ENTRE_DESPENSAS)
        return False, f"El hogar recibió despensa el {h.ultima_entrega}; vuelve a ser elegible el {prox}"
    return True, "elegible"


# Regla 2: el estado del lote depende de la caducidad
def estado_por_caducidad(caducidad: date, ref: date | None = None) -> str:
    ref = ref or hoy()
    if caducidad < ref:
        return "merma"
    if (caducidad - ref).days <= DIAS_PRIORITARIO:
        return "prioritario"
    return "disponible"


# Regla 5: cadena de frío
def resultado_inspeccion(p: Producto, temperatura, aprobado: bool) -> tuple[str, str | None]:
    if p.refrigerado:
        if temperatura is None:
            raise HTTPException(422, "Un producto refrigerado requiere temperatura de inspección")
        if Decimal(str(temperatura)) > TEMP_MAX_REFRIGERADO:
            return "rechazado", f"Cadena de frío: {temperatura} °C > {TEMP_MAX_REFRIGERADO} °C"
    if not aprobado:
        return "rechazado", "Rechazado en inspección"
    return "disponible", None


def _bloqueado_por_alergeno(p: Producto, h: Hogar) -> list[str]:
    return sorted(set(p.alergenos or []) & set(h.alergenos or []))


def _lotes_elegibles(db: Session, producto_id: int, d: Despensa, lock: bool = True):
    q = (select(Lote).where(Lote.producto_id == producto_id,
                            Lote.estado.in_(ESTADOS_ASIGNABLES),
                            Lote.cantidad_disponible > 0,
                            Lote.fecha_caducidad >= hoy())
         .order_by(Lote.fecha_caducidad, Lote.id))
    # Regla 2: un lote prioritario solo va a despensas que se entregan en <= 48 h
    if (d.fecha_programada - hoy()) > timedelta(hours=HORAS_PRIORIDAD_ENTREGA):
        q = q.where(Lote.estado != "prioritario")
    if lock:
        # Bloqueo de fila: dos réplicas del backend no pueden asignar la misma existencia
        q = q.with_for_update(of=Lote)
    return db.scalars(q).unique().all()


def _asignar(db: Session, d: Despensa, lote: Lote, cantidad: int, u: Usuario):
    lote.cantidad_disponible -= cantidad
    if lote.cantidad_disponible == 0:
        lote.estado = "asignado"
    existente = next((x for x in d.detalle if x.lote_id == lote.id), None)
    if existente:
        existente.cantidad += cantidad
    else:
        d.detalle.append(DespensaDetalle(lote_id=lote.id, cantidad=cantidad))
    events.registrar(db, "lote_asignado", lote.id, u.id, folio_lote=lote.folio, despensa=d.folio,
                     hogar_id=d.hogar_id, cantidad=cantidad)


# Regla 1 (FEFO) + Regla 4 (alérgenos): armado automático
def armar_fefo(db: Session, d: Despensa, u: Usuario) -> dict:
    h = d.hogar
    productos = db.scalars(select(Producto).where(Producto.activo, Producto.unidades_por_racion > 0)
                           .order_by(Producto.id)).all()
    omitidos, faltantes = [], []
    for p in productos:
        bloqueo = _bloqueado_por_alergeno(p, h)
        if bloqueo:
            omitidos.append({"producto": p.nombre, "alergenos": bloqueo})
            continue
        necesarias = math.ceil(p.unidades_por_racion * d.raciones)
        for lote in _lotes_elegibles(db, p.id, d):
            if necesarias == 0:
                break
            tomar = min(necesarias, lote.cantidad_disponible)
            _asignar(db, d, lote, tomar, u)
            necesarias -= tomar
        if necesarias:
            faltantes.append({"producto": p.nombre, "faltan": necesarias})
    if not d.detalle:
        raise HTTPException(409, "No hay existencias asignables para esta despensa")
    return {"omitidos_por_alergeno": omitidos, "faltantes": faltantes}


def agregar_manual(db: Session, d: Despensa, lote_id: int, cantidad: int, u: Usuario):
    lote = db.scalars(select(Lote).where(Lote.id == lote_id).with_for_update(of=Lote)).unique().one_or_none()
    if not lote:
        raise HTTPException(404, "Lote no encontrado")
    if lote.estado not in ESTADOS_ASIGNABLES or lote.fecha_caducidad < hoy():
        raise HTTPException(409, f"El lote {lote.folio} está en estado '{lote.estado}' y no es asignable")
    bloqueo = _bloqueado_por_alergeno(lote.producto, d.hogar)
    if bloqueo:
        raise HTTPException(409, f"Alérgeno bloqueado para el hogar: {', '.join(bloqueo)}")
    if lote.estado == "prioritario" and (d.fecha_programada - hoy()) > timedelta(hours=HORAS_PRIORIDAD_ENTREGA):
        raise HTTPException(409, "Lote prioritario: solo para despensas que se entregan en las próximas 48 h")
    elegibles = _lotes_elegibles(db, lote.producto_id, d)
    if elegibles and elegibles[0].id != lote.id and elegibles[0].fecha_caducidad < lote.fecha_caducidad:
        raise HTTPException(409, f"FEFO: debe usarse primero el lote {elegibles[0].folio} "
                                 f"(caduca {elegibles[0].fecha_caducidad})")
    if cantidad > lote.cantidad_disponible:
        raise HTTPException(409, f"Solo hay {lote.cantidad_disponible} unidades disponibles")
    _asignar(db, d, lote, cantidad, u)


def liberar(db: Session, d: Despensa, u: Usuario | None, excepto_lote: int | None = None):
    """Devuelve al inventario lo asignado (cancelación o no recogida)."""
    for det in d.detalle:
        lote = db.scalars(select(Lote).where(Lote.id == det.lote_id).with_for_update(of=Lote)).unique().one()
        if lote.id == excepto_lote or lote.estado in ("retirado", "merma"):
            continue
        lote.cantidad_disponible += det.cantidad
        lote.estado = estado_por_caducidad(lote.fecha_caducidad)
        events.registrar(db, "asignacion_liberada", lote.id, u.id if u else None, folio_lote=lote.folio,
                         despensa=d.folio, cantidad=det.cantidad, estado_despensa=d.estado)


def confirmar_entrega(db: Session, d: Despensa, u: Usuario):
    ahora = datetime.now(timezone.utc)
    d.entregada_en = ahora
    d.entregada_por = u.id
    d.hogar.ultima_entrega = hoy()
    for det in d.detalle:
        lote = det.lote
        events.registrar(db, "lote_entregado", lote.id, u.id, folio_lote=lote.folio, despensa=d.folio,
                         hogar_id=d.hogar_id, hogar_clave=d.hogar.clave, cantidad=det.cantidad)
        if lote.cantidad_disponible == 0:
            pendientes = db.scalar(select(func.count()).select_from(DespensaDetalle).join(Despensa)
                                   .where(DespensaDetalle.lote_id == lote.id, Despensa.id != d.id,
                                          Despensa.estado.in_(ESTADOS_DESPENSA_ABIERTA)))
            if not pendientes:
                lote.estado = "entregado"


# Regla 6: retiro sanitario
def retiro_sanitario(db: Session, lote: Lote, motivo: str, u: Usuario) -> dict:
    if lote.estado == "retirado":
        raise HTTPException(409, "El lote ya fue retirado")
    lote.estado = "retirado"
    lote.motivo = motivo
    lote.cantidad_disponible = 0
    afectadas = db.scalars(select(Despensa).join(DespensaDetalle)
                           .where(DespensaDetalle.lote_id == lote.id,
                                  Despensa.estado.in_(("aprobada", "en_preparacion", "lista")))
                           .with_for_update(of=Despensa)).unique().all()
    canceladas = []
    for d in afectadas:
        liberar(db, d, u, excepto_lote=lote.id)
        d.estado = "cancelada"
        d.motivo_cierre = f"Retiro sanitario del lote {lote.folio}"
        canceladas.append(d.folio)
    receptores = db.execute(select(Hogar.id, Hogar.clave, Hogar.responsable, Hogar.telefono, Despensa.folio,
                                   Despensa.entregada_en)
                            .join(Despensa, Despensa.hogar_id == Hogar.id).join(DespensaDetalle)
                            .where(DespensaDetalle.lote_id == lote.id, Despensa.estado == "entregada")).all()
    hogares = [{"hogar_id": r.id, "clave": r.clave, "responsable": r.responsable, "telefono": r.telefono,
                "despensa": r.folio, "entregada_en": r.entregada_en.isoformat() if r.entregada_en else None}
               for r in receptores]
    events.registrar(db, "lote_retirado", lote.id, u.id, folio_lote=lote.folio, motivo=motivo,
                     despensas_canceladas=canceladas, hogares_a_avisar=[h["clave"] for h in hogares])
    return {"despensas_canceladas": canceladas, "hogares_a_avisar": hogares}
