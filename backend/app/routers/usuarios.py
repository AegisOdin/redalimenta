from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Usuario
from ..schemas import UsuarioIn, UsuarioOut
from ..security import requiere, hash_password

router = APIRouter(prefix="/api/usuarios", tags=["usuarios"])
solo_admin = requiere("admin")


def _validar(d: UsuarioIn):
    if d.rol == "voluntario" and not d.ruta:
        raise HTTPException(422, "Un voluntario requiere ruta asignada")


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db), _=Depends(solo_admin)):
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()


@router.post("", response_model=UsuarioOut, status_code=201)
def crear(d: UsuarioIn, db: Session = Depends(get_db), _=Depends(solo_admin)):
    _validar(d)
    if not d.password:
        raise HTTPException(422, "La contraseña es obligatoria al crear (mínimo 10 caracteres)")
    u = Usuario(email=d.email.lower(), nombre=d.nombre, rol=d.rol, ruta=d.ruta, activo=d.activo,
                password_hash=hash_password(d.password))
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    return u


@router.put("/{uid}", response_model=UsuarioOut)
def actualizar(uid: int, d: UsuarioIn, db: Session = Depends(get_db), admin=Depends(solo_admin)):
    _validar(d)
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id and (d.rol != "admin" or not d.activo):
        raise HTTPException(409, "No puede quitarse a sí mismo el rol de administrador ni desactivarse")
    u.email, u.nombre, u.rol, u.ruta, u.activo = d.email.lower(), d.nombre, d.rol, d.ruta, d.activo
    if d.password:
        u.password_hash = hash_password(d.password)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    return u


@router.delete("/{uid}", status_code=204)
def desactivar(uid: int, db: Session = Depends(get_db), admin=Depends(solo_admin)):
    """Baja lógica: se conserva la autoría de lotes y despensas."""
    u = db.get(Usuario, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    if u.id == admin.id:
        raise HTTPException(409, "No puede desactivarse a sí mismo")
    u.activo = False
    db.commit()
