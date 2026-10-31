from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Usuario, LoginIntento
from ..schemas import Login, UsuarioOut
from ..security import verify_password, emitir_sesion, cerrar_sesion, usuario_actual

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(datos: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    email = datos.email.lower()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    # Límite de intentos compartido entre réplicas (en PostgreSQL, no en memoria)
    desde = datetime.now(timezone.utc) - timedelta(minutes=settings.login_ventana_min)
    fallidos = db.scalar(select(func.count()).select_from(LoginIntento)
                         .where(LoginIntento.email == email, LoginIntento.exito.is_(False), LoginIntento.ts >= desde))
    if fallidos >= settings.login_max_intentos:
        raise HTTPException(429, f"Demasiados intentos fallidos. Intente de nuevo en {settings.login_ventana_min} minutos")
    u = db.scalar(select(Usuario).where(Usuario.email == email))
    ok = bool(u and u.activo and verify_password(u.password_hash, datos.password))
    db.add(LoginIntento(email=email, ip=ip, exito=ok))
    db.commit()
    if not ok:
        raise HTTPException(401, "Credenciales inválidas")  # mensaje genérico: no revela si el usuario existe
    csrf = emitir_sesion(response, u)
    return {"usuario": UsuarioOut.model_validate(u), "csrf": csrf}


@router.post("/logout")
def logout(response: Response):
    cerrar_sesion(response)
    return {"ok": True}


@router.get("/me", response_model=UsuarioOut)
def me(u: Usuario = Depends(usuario_actual)):
    return u
