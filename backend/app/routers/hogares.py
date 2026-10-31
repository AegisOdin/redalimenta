from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import rules
from ..db import get_db
from ..models import Hogar, Despensa
from ..schemas import HogarIn, HogarOut
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api/hogares", tags=["hogares"])
gestion = requiere("trabajador_social")


def _filtro_ruta(q, u):
    # Un voluntario solo ve hogares de su ruta
    return q.where(Hogar.ruta == u.ruta) if u.rol == "voluntario" else q


def _out(h: Hogar):
    ok, motivo = rules.elegible(h, rules.hoy())
    return {**HogarOut.model_validate(h).model_dump(), "raciones": float(rules.raciones(h.integrantes)),
            "elegible": ok, "motivo_elegibilidad": motivo}


@router.get("")
def listar(q: str | None = Query(None, max_length=60), ruta: str | None = None,
           page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), u=Depends(usuario_actual)):
    base = _filtro_ruta(select(Hogar), u)
    if q:
        like = f"%{q}%"
        base = base.where(or_(Hogar.clave.ilike(like), Hogar.responsable.ilike(like), Hogar.colonia.ilike(like)))
    if ruta:
        base = base.where(Hogar.ruta == ruta)
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    filas = db.scalars(base.order_by(Hogar.clave).offset((page - 1) * size).limit(size)).all()
    return {"total": total, "page": page, "size": size, "items": [_out(h) for h in filas]}


@router.get("/{i}")
def obtener(i: int, db: Session = Depends(get_db), u=Depends(usuario_actual)):
    h = db.scalar(_filtro_ruta(select(Hogar).where(Hogar.id == i), u))
    if not h:
        raise HTTPException(404, "Hogar no encontrado")
    return _out(h)


@router.post("", status_code=201)
def crear(d: HogarIn, db: Session = Depends(get_db), _=Depends(gestion)):
    h = Hogar(**d.model_dump())
    db.add(h)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un hogar con la clave {d.clave}")
    return _out(h)


@router.put("/{i}")
def editar(i: int, d: HogarIn, db: Session = Depends(get_db), _=Depends(gestion)):
    h = db.get(Hogar, i)
    if not h:
        raise HTTPException(404, "Hogar no encontrado")
    for k, v in d.model_dump().items():
        setattr(h, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, f"Ya existe un hogar con la clave {d.clave}")
    return _out(h)


@router.delete("/{i}", status_code=204)
def baja(i: int, db: Session = Depends(get_db), _=Depends(gestion)):
    """Baja lógica: el historial de entregas es necesario para la trazabilidad sanitaria."""
    h = db.get(Hogar, i)
    if not h:
        raise HTTPException(404, "Hogar no encontrado")
    abiertas = db.scalar(select(func.count()).select_from(Despensa)
                         .where(Despensa.hogar_id == i, Despensa.estado.in_(rules.ESTADOS_DESPENSA_ABIERTA)))
    if abiertas:
        raise HTTPException(409, "El hogar tiene una despensa en curso; ciérrela antes de darlo de baja")
    h.activo = False
    db.commit()
