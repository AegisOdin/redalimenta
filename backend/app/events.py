"""Patrón outbox: el evento se inserta en PostgreSQL en la MISMA transacción que el cambio
de negocio. Un worker independiente lo publica en MongoDB con upsert por event_id."""
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from .models import Outbox


def registrar(db: Session, tipo: str, lote_id: int | None, usuario_id: int | None, **datos) -> uuid.UUID:
    eid = uuid.uuid4()
    db.add(Outbox(event_id=eid, tipo=tipo, lote_id=lote_id, payload={
        "event_id": str(eid), "tipo": tipo, "lote_id": lote_id, "usuario_id": usuario_id,
        "ts": datetime.now(timezone.utc).isoformat(), **datos}))
    return eid
