"""Tarea programada diaria (CronJob): estados por caducidad y despensas no recogidas en 72 h."""
from datetime import datetime, timedelta, timezone
import sys

from sqlalchemy import select

from . import events, rules
from .db import SessionLocal
from .logconf import setup
from .models import Lote, Despensa

log = setup("tareas")


def diario():
    with SessionLocal() as db:
        cambios = 0
        for l in db.scalars(select(Lote).where(Lote.estado.in_(("disponible", "prioritario", "asignado")))
                            .with_for_update(of=Lote)).unique():
            nuevo = rules.estado_por_caducidad(l.fecha_caducidad)
            if l.estado == "asignado":
                continue  # existencias ya comprometidas
            if nuevo != l.estado:
                events.registrar(db, "estado_lote", l.id, None, folio_lote=l.folio, anterior=l.estado, estado=nuevo)
                l.estado = nuevo
                cambios += 1
        limite = datetime.now(timezone.utc) - timedelta(hours=rules.HORAS_NO_RECOGIDA)
        no_rec = 0
        for d in db.scalars(select(Despensa).where(Despensa.estado == "lista", Despensa.lista_en < limite)
                            .with_for_update(of=Despensa)).unique():
            rules.liberar(db, d, None)
            d.estado, d.motivo_cierre = "no_recogida", "72 h sin recoger"
            events.registrar(db, "despensa_no_recogida", None, None, despensa=d.folio, hogar_id=d.hogar_id)
            no_rec += 1
        db.commit()
        log.info("tarea_diaria", extra={"lotes_actualizados": cambios, "despensas_no_recogidas": no_rec})


def reproyectar(desde: str):
    """Reconciliación MongoDB tras restaurarlo: marca como pendientes los eventos outbox creados desde <desde>
    (ISO-8601). El worker los reaplica; la idempotencia por event_id evita duplicados."""
    from sqlalchemy import update
    from .models import Outbox
    ts = datetime.fromisoformat(desde)
    with SessionLocal() as db:
        n = db.execute(update(Outbox).where(Outbox.creado_en >= ts).values(publicado_en=None)).rowcount
        db.commit()
    log.info("reproyeccion", extra={"desde": desde, "eventos": n})
    print(f"{n} eventos marcados para reproyectar desde {desde}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "reproyectar":
        reproyectar(sys.argv[2]); sys.exit(0)
    {"diario": diario}[sys.argv[1] if len(sys.argv) > 1 else "diario"]()
