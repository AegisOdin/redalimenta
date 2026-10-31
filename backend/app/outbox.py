"""Worker del patrón outbox. Publica en MongoDB los eventos confirmados en PostgreSQL.
Idempotencia: bitacora_eventos tiene índice único en event_id y el expediente solo agrega el evento
si su event_id no está ya en el arreglo. Reintentar nunca duplica."""
import logging
import os
import time
from datetime import datetime, timezone

from prometheus_client import start_http_server
from pymongo.errors import DuplicateKeyError, PyMongoError
from sqlalchemy import select, func, text

from .db import SessionLocal
from .logconf import setup
from .metrics import OUTBOX_PEND, OUTBOX_PUB, OUTBOX_ERR, DEP_UP
from .models import Outbox
from .mongo import mdb

log = setup("outbox")
LOTE = int(os.getenv("OUTBOX_BATCH", "50"))
ESPERA = float(os.getenv("OUTBOX_POLL_SECONDS", "1"))


def aplicar(ev: dict):
    db = mdb()
    eid = ev["event_id"]
    doc = {k: v for k, v in ev.items() if v is not None}
    try:
        db.bitacora_eventos.insert_one(dict(doc))
    except DuplicateKeyError:
        pass  # ya aplicado en un intento anterior
    if not ev.get("folio_lote") or ev.get("lote_id") is None:
        return
    s, add = {}, {}
    t = ev["tipo"]
    if t == "lote_recibido":
        s.update({k: ev.get(k) for k in ("producto", "categoria", "refrigerado", "alergenos", "donante",
                                         "donante_tipo", "cantidad", "fecha_caducidad")})
        s["estado"] = "recibido"
    elif t == "lote_inspeccionado":
        s["inspeccion"] = {"checklist": ev.get("checklist", {}), "temperatura_c": ev.get("temperatura_c"),
                           "resultado": ev.get("resultado"), "observaciones": ev.get("observaciones"),
                           "ts": ev["ts"], "usuario_id": ev.get("usuario_id")}
        s["estado"] = ev.get("resultado")
    elif t == "lote_entregado":
        add["hogares_receptores"] = {"hogar_id": ev["hogar_id"], "clave": ev.get("hogar_clave"),
                                     "despensa": ev.get("despensa")}
    elif t == "lote_retirado":
        s.update({"estado": "retirado", "retiro": {"motivo": ev.get("motivo"), "ts": ev["ts"],
                                                   "hogares_a_avisar": ev.get("hogares_a_avisar", [])}})
    elif t == "estado_lote":
        s["estado"] = ev.get("estado")
    elif t == "lote_eliminado":
        s["estado"] = "eliminado"
    upd = {"$push": {"eventos": {k: v for k, v in doc.items() if k not in ("folio_lote",)}},
           "$setOnInsert": {"lote_id": ev["lote_id"], "creado_en": ev["ts"]}}
    s = {k: v for k, v in s.items() if v is not None}
    if s:
        upd["$set"] = s
    if add:
        upd["$addToSet"] = add
    try:
        db.expediente_lote.update_one({"folio_lote": ev["folio_lote"], "eventos.event_id": {"$ne": eid}},
                                      upd, upsert=True)
    except DuplicateKeyError:
        pass  # el expediente existe y ya contiene este event_id


def ciclo() -> int:
    with SessionLocal() as db:
        filas = db.scalars(select(Outbox).where(Outbox.publicado_en.is_(None)).order_by(Outbox.id)
                           .limit(LOTE).with_for_update(skip_locked=True)).all()
        hechos = 0
        for o in filas:
            try:
                aplicar(o.payload)
            except PyMongoError as e:
                o.intentos += 1
                o.ultimo_error = str(e)[:500]
                OUTBOX_ERR.inc()
                DEP_UP.labels("mongo").set(0)
                db.commit()
                # la métrica de pendientes debe reflejar el atraso también mientras MongoDB está caído
                OUTBOX_PEND.set(db.scalar(select(func.count()).select_from(Outbox).where(Outbox.publicado_en.is_(None))))
                log.warning("mongo_no_disponible", extra={"event_id": str(o.event_id), "intentos": o.intentos})
                return -1  # se detiene el lote para conservar el orden de eventos
            o.publicado_en = datetime.now(timezone.utc)
            hechos += 1
            OUTBOX_PUB.inc()
        DEP_UP.labels("mongo").set(1)
        db.commit()
        OUTBOX_PEND.set(db.scalar(select(func.count()).select_from(Outbox).where(Outbox.publicado_en.is_(None))))
        return hechos


def main():
    start_http_server(int(os.getenv("METRICS_PORT", "9100")))
    log.info("outbox_worker_iniciado")
    espera_error = 1.0
    while True:
        try:
            n = ciclo()
        except Exception as e:  # PostgreSQL caído u otro error: reintentar con backoff
            log.error("ciclo_fallido", extra={"error": str(e)[:200]})
            n = -1
        if n < 0:
            time.sleep(espera_error)
            espera_error = min(espera_error * 2, 30)
        else:
            espera_error = 1.0
            if n < LOTE:
                time.sleep(ESPERA)


if __name__ == "__main__":
    main()
