"""Lecturas sobre MongoDB: expediente del lote, hogares receptores y bitácora consultable.
PostgreSQL es la fuente de verdad; MongoDB es la proyección histórica alimentada por el outbox."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import PyMongoError
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Lote, Outbox
from ..mongo import mdb
from ..security import requiere

router = APIRouter(prefix="/api/trazabilidad", tags=["trazabilidad"])
lectura = requiere("admin", "coordinador", "trabajador_social")


def _mongo(fn):
    try:
        return fn()
    except PyMongoError:
        raise HTTPException(503, "El expediente no está disponible temporalmente (MongoDB). "
                                 "Las operaciones del almacén continúan y se sincronizarán al volver.")


@router.get("/lotes/{folio}")
def expediente(folio: str, db: Session = Depends(get_db), _=Depends(lectura)):
    doc = _mongo(lambda: mdb().expediente_lote.find_one({"folio_lote": folio}, {"_id": 0}))
    lote = db.scalar(select(Lote).where(Lote.folio == folio))
    if not doc and not lote:
        raise HTTPException(404, "Lote no encontrado")
    pendientes = 0
    if lote:
        pendientes = db.scalar(select(func.count()).select_from(Outbox)
                               .where(Outbox.lote_id == lote.id, Outbox.publicado_en.is_(None)))
    if doc:
        doc["eventos"] = sorted(doc.get("eventos", []), key=lambda e: e.get("ts", ""))
    return {"expediente": doc, "eventos_pendientes_de_sincronizar": pendientes,
            "estado_actual": lote.estado if lote else None}


@router.get("/lotes/{folio}/hogares")
def hogares_receptores(folio: str, _=Depends(lectura)):
    """¿Qué hogares recibieron el lote X? (índice eventos.hogar_id / tipo en bitacora_eventos)"""
    cur = _mongo(lambda: list(mdb().bitacora_eventos.find(
        {"folio_lote": folio, "tipo": "lote_entregado"},
        {"_id": 0, "hogar_id": 1, "hogar_clave": 1, "despensa": 1, "cantidad": 1, "ts": 1}).sort("ts", 1)))
    return {"folio_lote": folio, "hogares": cur}


@router.get("/bitacora")
def bitacora(tipo: str | None = None, hogar_id: int | None = None, folio_lote: str | None = None,
             page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100), _=Depends(lectura)):
    filtro = {}
    if tipo:
        filtro["tipo"] = tipo
    if hogar_id:
        filtro["hogar_id"] = hogar_id
    if folio_lote:
        filtro["folio_lote"] = folio_lote

    def q():
        col = mdb().bitacora_eventos
        total = col.count_documents(filtro)
        items = list(col.find(filtro, {"_id": 0}).sort("ts", -1).skip((page - 1) * size).limit(size))
        return {"total": total, "page": page, "size": size, "items": items}
    return _mongo(q)
