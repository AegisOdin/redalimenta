"""Script idempotente: colecciones con validación JSON Schema e índices. Se ejecuta en el Job de migración
con un usuario con rol dbAdmin (la app en ejecución solo tiene readWrite)."""
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import CollectionInvalid

from .mongo import mdb

EXPEDIENTE_SCHEMA = {"$jsonSchema": {
    "bsonType": "object", "required": ["folio_lote", "lote_id", "eventos"],
    "properties": {
        "folio_lote": {"bsonType": "string"}, "lote_id": {"bsonType": ["int", "long"]},
        "producto": {"bsonType": "string"}, "categoria": {"bsonType": "string"},
        "inspeccion": {"bsonType": "object", "description": "checklist flexible por tipo de producto"},
        "hogares_receptores": {"bsonType": "array"},
        "eventos": {"bsonType": "array", "items": {"bsonType": "object", "required": ["event_id", "tipo", "ts"],
                    "properties": {"event_id": {"bsonType": "string"}, "tipo": {"bsonType": "string"},
                                   "ts": {"bsonType": "string"}}}}}}}

BITACORA_SCHEMA = {"$jsonSchema": {
    "bsonType": "object", "required": ["event_id", "tipo", "ts"],
    "properties": {"event_id": {"bsonType": "string"}, "tipo": {"bsonType": "string"},
                   "ts": {"bsonType": "string"}, "lote_id": {"bsonType": ["int", "long", "null"]},
                   "hogar_id": {"bsonType": ["int", "long", "null"]}}}}


def main():
    db = mdb()
    for nombre, schema in (("expediente_lote", EXPEDIENTE_SCHEMA), ("bitacora_eventos", BITACORA_SCHEMA)):
        try:
            db.create_collection(nombre, validator=schema, validationLevel="strict")
        except CollectionInvalid:
            db.command("collMod", nombre, validator=schema, validationLevel="strict")
    db.expediente_lote.create_index([("folio_lote", ASCENDING)], unique=True, name="ux_folio_lote")
    db.expediente_lote.create_index([("eventos.hogar_id", ASCENDING)], name="ix_eventos_hogar")
    db.expediente_lote.create_index([("eventos.event_id", ASCENDING)], name="ix_eventos_event_id")
    db.bitacora_eventos.create_index([("event_id", ASCENDING)], unique=True, name="ux_event_id")
    db.bitacora_eventos.create_index([("hogar_id", ASCENDING), ("ts", DESCENDING)], name="ix_hogar_ts")
    db.bitacora_eventos.create_index([("folio_lote", ASCENDING), ("tipo", ASCENDING)], name="ix_folio_tipo")
    db.bitacora_eventos.create_index([("tipo", ASCENDING), ("ts", DESCENDING)], name="ix_tipo_ts")
    print("MongoDB: colecciones e índices listos")


if __name__ == "__main__":
    main()
