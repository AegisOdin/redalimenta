from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import events, rules
from ..db import get_db
from ..models import Despensa, Hogar
from ..schemas import DespensaIn, TransicionIn, ItemManualIn
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api/despensas", tags=["despensas"])


def _out(d: Despensa) -> dict:
    return {"id": d.id, "folio": d.folio, "estado": d.estado, "raciones": float(d.raciones),
            "fecha_programada": d.fecha_programada, "motivo_cierre": d.motivo_cierre,
            "hogar": {"id": d.hogar.id, "clave": d.hogar.clave, "responsable": d.hogar.responsable,
                      "ruta": d.hogar.ruta, "alergenos": d.hogar.alergenos, "colonia": d.hogar.colonia},
            "creado_en": d.creado_en, "lista_en": d.lista_en, "entregada_en": d.entregada_en,
            "detalle": [{"lote_id": x.lote_id, "folio_lote": x.lote.folio, "producto": x.lote.producto.nombre,
                         "caducidad": x.lote.fecha_caducidad, "cantidad": x.cantidad} for x in d.detalle],
            "transiciones": sorted({dst for (src, dst) in rules.TRANSICIONES if src == d.estado})}


def _get(db, i, u, lock=False) -> Despensa:
    q = select(Despensa).where(Despensa.id == i)
    if u.rol == "voluntario":
        q = q.join(Hogar).where(Hogar.ruta == u.ruta)
    if lock:
        q = q.with_for_update(of=Despensa)
    d = db.scalars(q).unique().one_or_none()
    if not d:
        raise HTTPException(404, "Despensa no encontrada")
    return d


@router.get("")
def listar(estado: str | None = None, q: str | None = Query(None, max_length=60),
           page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), u=Depends(usuario_actual)):
    base = select(Despensa).join(Hogar)
    if u.rol == "voluntario":  # solo su ruta y solo lo que le toca entregar o ya entregó
        base = base.where(Hogar.ruta == u.ruta, Despensa.estado.in_(("lista", "entregada")))
    if estado:
        base = base.where(Despensa.estado == estado)
    if q:
        like = f"%{q}%"
        base = base.where((Despensa.folio.ilike(like)) | (Hogar.clave.ilike(like)) | (Hogar.responsable.ilike(like)))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    filas = db.scalars(base.order_by(Despensa.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"total": total, "page": page, "size": size, "items": [_out(d) for d in filas]}


@router.get("/{i}")
def obtener(i: int, db: Session = Depends(get_db), u=Depends(usuario_actual)):
    return _out(_get(db, i, u))


@router.post("", status_code=201)
def solicitar(d: DespensaIn, db: Session = Depends(get_db), u=Depends(requiere("trabajador_social"))):
    h = db.get(Hogar, d.hogar_id)
    if not h or not h.activo:
        raise HTTPException(422, "Hogar inexistente o inactivo")
    if d.fecha_programada < date.today():
        raise HTTPException(422, "La fecha programada no puede estar en el pasado")
    seq = db.scalar(text("SELECT nextval('folio_despensa_seq')"))
    o = Despensa(folio=f"D-{date.today():%y%m}-{seq:05d}", hogar_id=h.id, estado="solicitada",
                 raciones=rules.raciones(h.integrantes), fecha_programada=d.fecha_programada, solicitada_por=u.id)
    db.add(o)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "El hogar ya tiene una despensa en curso")
    return _out(_get(db, o.id, u))


@router.post("/{i}/transicion/{destino}")
def transicion(i: int, destino: str, t: TransicionIn, db: Session = Depends(get_db), u=Depends(usuario_actual)):
    d = _get(db, i, u, lock=True)
    roles = rules.TRANSICIONES.get((d.estado, destino))
    if roles is None:
        raise HTTPException(409, f"Transición inválida: {d.estado} → {destino}")
    if u.rol != "admin" and u.rol not in roles:  # el administrador puede ejecutar cualquier transición válida
        raise HTTPException(403, f"El rol '{u.rol}' no puede pasar la despensa de {d.estado} a {destino}")
    extra = {}
    if destino == "aprobada":
        ok, motivo = rules.elegible(d.hogar, d.fecha_programada)
        if not ok:
            raise HTTPException(409, f"No elegible: {motivo}. Debe rechazarse.")
        d.raciones = rules.raciones(d.hogar.integrantes)
        d.aprobada_por = u.id
    elif destino == "en_preparacion":
        d.preparada_por = u.id
        d.estado = destino
        extra = rules.armar_fefo(db, d, u)
    elif destino == "lista":
        if not d.detalle:
            raise HTTPException(409, "La despensa no tiene productos asignados")
        d.lista_en = datetime.now(timezone.utc)
    elif destino == "entregada":
        rules.confirmar_entrega(db, d, u)
    elif destino in ("cancelada", "no_recogida", "rechazada"):
        if destino != "rechazada" and not t.motivo:
            raise HTTPException(422, "Indique el motivo")
        rules.liberar(db, d, u)
        d.motivo_cierre = t.motivo or "No cumple la regla de 14 días"
    d.estado = destino
    events.registrar(db, "despensa_" + destino, None, u.id, despensa=d.folio, hogar_id=d.hogar_id,
                     motivo=t.motivo)
    db.commit()
    return {"despensa": _out(_get(db, i, u)), **extra}


@router.post("/{i}/items")
def agregar_item(i: int, it: ItemManualIn, db: Session = Depends(get_db), u=Depends(requiere("coordinador"))):
    """Ajuste manual del armado: valida FEFO, alérgenos y prioridad aunque se evite la interfaz."""
    d = _get(db, i, u, lock=True)
    if d.estado != "en_preparacion":
        raise HTTPException(409, "Solo se agregan productos a despensas en preparación")
    rules.agregar_manual(db, d, it.lote_id, it.cantidad, u)
    db.commit()
    return _out(_get(db, i, u))
