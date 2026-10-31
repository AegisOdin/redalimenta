import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from .config import settings
from .logconf import setup, request_id
from .metrics import MetricsMiddleware
from .routers import auth, usuarios, catalogos, lotes, hogares, despensas, trazabilidad, reportes, diag

log = setup()
app = FastAPI(title="RedAlimenta API", version=settings.app_version,
              docs_url="/api/docs" if settings.app_env == "dev" else None, openapi_url="/api/openapi.json"
              if settings.app_env == "dev" else None)

if settings.allowed_origins:  # CORS solo con orígenes explícitos (misma origen por defecto)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["content-type", "x-csrf-token"])
app.add_middleware(MetricsMiddleware)


@app.middleware("http")
async def correlacion(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request_id.set(rid)
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["x-request-id"] = rid
    resp.headers["x-content-type-options"] = "nosniff"
    if request.url.path not in ("/healthz", "/readyz", "/metrics"):
        log.info("http", extra={"method": request.method, "path": request.url.path, "status": resp.status_code,
                                "ms": round((time.perf_counter() - t0) * 1000, 1)})
    return resp


@app.exception_handler(RequestValidationError)
async def validacion(_: Request, exc: RequestValidationError):
    errores = [{"campo": ".".join(str(x) for x in e["loc"][1:]), "mensaje": e["msg"]} for e in exc.errors()]
    return JSONResponse({"detail": "Datos inválidos", "errores": errores}, status_code=422)


@app.exception_handler(OperationalError)
async def bd_caida(_: Request, exc: OperationalError):
    log.error("postgres_no_disponible", extra={"error": str(exc.orig)[:200]})
    return JSONResponse({"detail": "Servicio de datos no disponible temporalmente, intente de nuevo"}, status_code=503)


@app.exception_handler(Exception)
async def generico(_: Request, exc: Exception):
    log.exception("error_no_controlado")  # el detalle queda en logs, no se expone al cliente
    return JSONResponse({"detail": "Error interno"}, status_code=500)


for r in (auth, usuarios, catalogos, lotes, hogares, despensas, trazabilidad, reportes, diag):
    app.include_router(r.router)
