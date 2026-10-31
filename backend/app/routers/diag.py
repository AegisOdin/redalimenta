from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db, engine
from ..metrics import DEP_UP
from ..mongo import client

router = APIRouter(tags=["diagnostico"])


@router.get("/healthz")
def healthz():
    """Liveness: solo verifica que el proceso responde. NO consulta bases de datos para que una
    caída temporal de PostgreSQL/MongoDB no provoque reinicios masivos."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    """Readiness: PostgreSQL es indispensable (fuente de verdad). MongoDB no: si cae, el outbox
    acumula eventos y la app sigue atendiendo."""
    estado = {"postgres": False, "mongo": False}
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
        estado["postgres"] = True
    except Exception:
        pass
    try:
        client().admin.command("ping")
        estado["mongo"] = True
    except Exception:
        pass
    DEP_UP.labels("postgres").set(int(estado["postgres"]))
    DEP_UP.labels("mongo").set(int(estado["mongo"]))
    code = 200 if estado["postgres"] else 503
    return JSONResponse(estado, status_code=code)


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/version")
def version():
    return {"version": settings.app_version, "ambiente": settings.app_env}


@router.get("/api/diag/replica")
def replica(db: Session = Depends(get_db)):
    """Identificador temporal de réplica para demostrar balanceo. Se desactiva con DIAG_REPLICA=false."""
    if not settings.diag_replica:
        raise HTTPException(404, "No disponible")
    n = db.execute(text("SELECT count(*) FROM lotes WHERE estado IN ('disponible','prioritario')")).scalar()
    return {"replica": settings.hostname, "version": settings.app_version, "lotes_asignables": n}
