from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_, text
from sqlalchemy.orm import Session

from .. import events, rules
from ..db import get_db
from ..models import Lote, Producto, Donante, DespensaDetalle
from ..schemas import LoteIn, LoteUpdate, LoteOut, InspeccionIn, RetiroIn
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api/lotes", tags=["lotes"])
inventario = requiere("coordinador")
lectura = requiere("admin", "coordinador", "trabajador_social")


def out(l: Lote) -> LoteOut:
    return LoteOut(id=l.id, folio=l.folio, producto_id=l.producto_id, producto_nombre=l.producto.nombre,
                   categoria=l.producto.categoria, donante_id=l.donante_id, donante_nombre=l.donante.nombre,
                   cantidad_inicial=l.cantidad_inicial, cantidad_disponible=l.cantidad_disponible,
                   fecha_recepcion=l.fecha_recepcion, fecha_caducidad=l.fecha_caducidad, estado=l.estado,
                   temperatura_c=l.temperatura_c, motivo=l.motivo)


def _get(db, i, lock=False) -> Lote:
    q = select(Lote).where(Lote.id == i)
    if lock:
        q = q.with_for_update(of=Lote)
    l = db.scalars(q).unique().one_or_none()
    if not l:
        raise HTTPException(404, "Lote no encontrado")
    return l


@router.get("")
def listar(q: str | None = Query(None, max_length=60), estado: str | None = None,
           page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), _=Depends(lectura)):
    base = select(Lote).join(Producto).join(Donante)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Lote.folio.ilike(like), Producto.nombre.ilike(like), Donante.nombre.ilike(like)))
    if estado:
        base = base.where(Lote.estado == estado)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    filas = db.scalars(base.order_by(Lote.fecha_caducidad, Lote.id).offset((page - 1) * size).limit(size)).unique().all()
    return {"total": total, "page": page, "size": size, "items": [out(l) for l in filas]}


@router.get("/{i}", response_model=LoteOut)
def obtener(i: int, db: Session = Depends(get_db), _=Depends(lectura)):
    return out(_get(db, i))


@router.post("", response_model=LoteOut, status_code=201)
def recibir(d: LoteIn, db: Session = Depends(get_db), u=Depends(inventario)):
    p = db.get(Producto, d.producto_id)
    don = db.get(Donante, d.donante_id)
    if not p or not p.activo:
        raise HTTPException(422, "Producto inexistente o inactivo")
    if not don or not don.activo:
        raise HTTPException(422, "Donante inexistente o inactivo")
    if d.fecha_caducidad < date.today():
        raise HTTPException(422, "No se reciben lotes ya caducados")
    seq = db.scalar(text("SELECT nextval('folio_lote_seq')"))  # secuencia: segura con varias réplicas
    folio = f"L-{date.today():%y%m}-{seq:05d}"
    l = Lote(folio=folio, producto_id=p.id, donante_id=don.id, cantidad_inicial=d.cantidad_inicial,
             cantidad_disponible=d.cantidad_inicial, fecha_caducidad=d.fecha_caducidad,
             estado="recibido", creado_por=u.id)
    db.add(l)
    db.flush()
    events.registrar(db, "lote_recibido", l.id, u.id, folio_lote=folio, producto=p.nombre, categoria=p.categoria,
                     refrigerado=p.refrigerado, alergenos=p.alergenos, donante=don.nombre, donante_tipo=don.tipo,
                     cantidad=d.cantidad_inicial, fecha_caducidad=str(d.fecha_caducidad))
    db.commit()  # lote + evento outbox en la misma transacción
    db.refresh(l)
    return out(l)


@router.put("/{i}", response_model=LoteOut)
def editar(i: int, d: LoteUpdate, db: Session = Depends(get_db), u=Depends(inventario)):
    l = _get(db, i, lock=True)
    if l.estado not in ("recibido", "en_inspeccion"):
        raise HTTPException(409, "Solo se corrigen lotes antes de quedar disponibles")
    cambios = d.model_dump(exclude_none=True)
    if "cantidad_inicial" in cambios:
        l.cantidad_inicial = l.cantidad_disponible = cambios["cantidad_inicial"]
    if "fecha_caducidad" in cambios:
        if cambios["fecha_caducidad"] < l.fecha_recepcion:
            raise HTTPException(422, "La caducidad no puede ser anterior a la recepción")
        l.fecha_caducidad = cambios["fecha_caducidad"]
    if "donante_id" in cambios:
        if not db.get(Donante, cambios["donante_id"]):
            raise HTTPException(422, "Donante inexistente")
        l.donante_id = cambios["donante_id"]
    events.registrar(db, "lote_corregido", l.id, u.id, folio_lote=l.folio,
                     cambios={k: str(v) for k, v in cambios.items()})
    db.commit()
    return out(_get(db, i))


@router.post("/{i}/iniciar-inspeccion", response_model=LoteOut)
def iniciar_inspeccion(i: int, db: Session = Depends(get_db), u=Depends(inventario)):
    l = _get(db, i, lock=True)
    if l.estado != "recibido":
        raise HTTPException(409, f"Transición inválida: {l.estado} → en_inspeccion")
    l.estado = "en_inspeccion"
    events.registrar(db, "inspeccion_iniciada", l.id, u.id, folio_lote=l.folio)
    db.commit()
    return out(_get(db, i))


@router.post("/{i}/inspeccion", response_model=LoteOut)
def inspeccionar(i: int, d: InspeccionIn, db: Session = Depends(get_db), u=Depends(inventario)):
    l = _get(db, i, lock=True)
    if l.estado not in ("recibido", "en_inspeccion"):
        raise HTTPException(409, f"El lote ya fue inspeccionado (estado {l.estado})")
    resultado, motivo = rules.resultado_inspeccion(l.producto, d.temperatura_c, d.aprobado)
    if resultado == "disponible":
        resultado = rules.estado_por_caducidad(l.fecha_caducidad)
        if resultado == "merma":
            motivo = "Caducó antes de liberarse"
    l.estado, l.temperatura_c, l.motivo = resultado, d.temperatura_c, motivo or d.observaciones
    if resultado in ("rechazado", "merma"):
        l.cantidad_disponible = l.cantidad_disponible if resultado == "merma" else 0
    # El checklist es flexible por tipo de producto: se guarda completo en el expediente de MongoDB
    events.registrar(db, "lote_inspeccionado", l.id, u.id, folio_lote=l.folio, resultado=resultado,
                     motivo=motivo, temperatura_c=float(d.temperatura_c) if d.temperatura_c is not None else None,
                     checklist=d.checklist, observaciones=d.observaciones, categoria=l.producto.categoria)
    db.commit()
    return out(_get(db, i))


@router.post("/{i}/retiro-sanitario")
def retiro(i: int, d: RetiroIn, db: Session = Depends(get_db), u=Depends(requiere("admin"))):
    l = _get(db, i, lock=True)
    r = rules.retiro_sanitario(db, l, d.motivo, u)
    db.commit()
    return {"lote": out(_get(db, i)), **r}


@router.delete("/{i}", status_code=204)
def eliminar(i: int, db: Session = Depends(get_db), u=Depends(inventario)):
    """Baja física solo si el lote aún no tiene historia operativa (capturado por error)."""
    l = _get(db, i, lock=True)
    usado = db.scalar(select(func.count()).select_from(DespensaDetalle).where(DespensaDetalle.lote_id == i))
    if l.estado != "recibido" or usado:
        raise HTTPException(409, "Solo se eliminan lotes recién recibidos sin uso; use retiro o merma")
    events.registrar(db, "lote_eliminado", l.id, u.id, folio_lote=l.folio)
    db.delete(l)
    db.commit()
