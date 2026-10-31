"""Autenticación por cookie HttpOnly firmada (JWT HS256) + protección CSRF de doble envío.
Sin estado de sesión local: cualquier réplica valida el token con el secreto compartido."""
from datetime import datetime, timedelta, timezone
import secrets

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import Usuario

ph = PasswordHasher()  # Argon2id con sal aleatoria
COOKIE = "ra_session"
CSRF_COOKIE = "ra_csrf"
CSRF_HEADER = "x-csrf-token"


def hash_password(p: str) -> str:
    return ph.hash(p)


def verify_password(h: str, p: str) -> bool:
    try:
        return ph.verify(h, p)
    except (VerifyMismatchError, InvalidHashError):
        return False


def emitir_sesion(resp: Response, u: Usuario) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.session_minutes)
    csrf = secrets.token_urlsafe(24)
    token = jwt.encode({"sub": str(u.id), "rol": u.rol, "csrf": csrf, "exp": exp},
                       settings.session_secret, algorithm="HS256")
    common = dict(secure=settings.cookie_secure, samesite="strict", path="/",
                  max_age=settings.session_minutes * 60)
    resp.set_cookie(COOKIE, token, httponly=True, **common)
    resp.set_cookie(CSRF_COOKIE, csrf, httponly=False, **common)  # legible por la SPA
    return csrf


def cerrar_sesion(resp: Response):
    resp.delete_cookie(COOKIE, path="/")
    resp.delete_cookie(CSRF_COOKIE, path="/")


def usuario_actual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "No autenticado")
    try:
        data = jwt.decode(token, settings.session_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Sesión expirada")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Sesión inválida")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        enviado = request.headers.get(CSRF_HEADER)
        if not enviado or not secrets.compare_digest(enviado, data.get("csrf", "")):
            raise HTTPException(403, "Token CSRF inválido")
    u = db.get(Usuario, int(data["sub"]))
    if not u or not u.activo:
        raise HTTPException(401, "Usuario inactivo")
    return u


def requiere(*roles: str):
    """Autorización en servidor por rol."""
    def dep(u: Usuario = Depends(usuario_actual)) -> Usuario:
        if u.rol not in roles:
            raise HTTPException(403, f"El rol '{u.rol}' no tiene permiso para esta operación")
        return u
    return dep
