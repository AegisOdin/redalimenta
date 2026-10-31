from pymongo import MongoClient

from .config import settings

_client: MongoClient | None = None


def client() -> MongoClient:
    global _client
    if _client is None:
        # TLS y CA se definen en la URL (tls=true&tlsCAFile=...) en producción
        _client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=2000,
                              connectTimeoutMS=2000, appname=f"redalimenta-{settings.hostname}")
    return _client


def mdb():
    return client()[settings.mongo_db]
