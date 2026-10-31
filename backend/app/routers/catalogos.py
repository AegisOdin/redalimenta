from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Donante, Producto, ALERGENOS, CATEGORIAS
from ..schemas import DonanteIn, DonanteOut, ProductoIn, ProductoOut
from ..security import requiere, usuario_actual

router = APIRouter(prefix="/api", tags=["catalogos"])
solo_admin = requiere("admin")


def _commit(db, msg):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, msg)


@router.get("/catalogos/meta")
def meta(_=Depends(usuario_actual)):
    return {"alergenos": ALERGENOS, "categorias": CATEGORIAS}


@router.get("/donantes", response_model=list[DonanteOut])
def donantes(db: Session = Depends(get_db), _=Depends(usuario_actual)):
    return db.scalars(select(Donante).order_by(Donante.nombre)).all()


@router.post("/donantes", response_model=DonanteOut, status_code=201)
def crear_donante(d: DonanteIn, db: Session = Depends(get_db), _=Depends(requiere("admin", "coordinador"))):
    o = Donante(**d.model_dump())
    db.add(o)
    _commit(db, "Ya existe un donante con ese nombre")
    return o


@router.put("/donantes/{i}", response_model=DonanteOut)
def editar_donante(i: int, d: DonanteIn, db: Session = Depends(get_db), _=Depends(solo_admin)):
    o = db.get(Donante, i)
    if not o:
        raise HTTPException(404, "Donante no encontrado")
    for k, v in d.model_dump().items():
        setattr(o, k, v)
    _commit(db, "Ya existe un donante con ese nombre")
    return o


@router.delete("/donantes/{i}", status_code=204)
def baja_donante(i: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    o = db.get(Donante, i)
    if not o:
        raise HTTPException(404, "Donante no encontrado")
    o.activo = False  # baja lógica: los lotes históricos lo referencian
    db.commit()


@router.get("/productos", response_model=list[ProductoOut])
def productos(db: Session = Depends(get_db), _=Depends(usuario_actual)):
    return db.scalars(select(Producto).order_by(Producto.nombre)).all()


@router.post("/productos", response_model=ProductoOut, status_code=201)
def crear_producto(d: ProductoIn, db: Session = Depends(get_db), _=Depends(solo_admin)):
    if d.categoria == "refrigerado" and not d.refrigerado:
        raise HTTPException(422, "La categoría refrigerado exige marcar el producto como refrigerado")
    o = Producto(**d.model_dump())
    db.add(o)
    _commit(db, "Ya existe un producto con ese nombre")
    return o


@router.put("/productos/{i}", response_model=ProductoOut)
def editar_producto(i: int, d: ProductoIn, db: Session = Depends(get_db), _=Depends(solo_admin)):
    o = db.get(Producto, i)
    if not o:
        raise HTTPException(404, "Producto no encontrado")
    for k, v in d.model_dump().items():
        setattr(o, k, v)
    _commit(db, "Ya existe un producto con ese nombre")
    return o


@router.delete("/productos/{i}", status_code=204)
def baja_producto(i: int, db: Session = Depends(get_db), _=Depends(solo_admin)):
    o = db.get(Producto, i)
    if not o:
        raise HTTPException(404, "Producto no encontrado")
    o.activo = False
    db.commit()
