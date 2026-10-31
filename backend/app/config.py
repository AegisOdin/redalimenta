"""Configuración leída exclusivamente de variables de entorno (12-factor).
Los valores sensibles llegan desde Secrets de Kubernetes; nunca se versionan."""
import os
import socket


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "si")


class Settings:
    app_env: str = os.getenv("APP_ENV", "dev")
    app_version: str = os.getenv("APP_VERSION", "0.0.0-local")
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/redalimenta")
    mongo_url: str = os.getenv("MONGO_URL", "mongodb://localhost:27017/redalimenta")
    mongo_db: str = os.getenv("MONGO_DB", "redalimenta")
    session_secret: str = os.getenv("SESSION_SECRET", "")
    session_minutes: int = int(os.getenv("SESSION_MINUTES", "30"))
    cookie_secure: bool = _bool("COOKIE_SECURE", True)
    allowed_origins: list[str] = [o for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o]
    # Estrategia de conexiones: pool pequeño por réplica. 6 réplicas x (5+5) = 60 < max_connections.
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    login_max_intentos: int = int(os.getenv("LOGIN_MAX_INTENTOS", "5"))
    login_ventana_min: int = int(os.getenv("LOGIN_VENTANA_MIN", "15"))
    diag_replica: bool = _bool("DIAG_REPLICA", False)
    hostname: str = socket.gethostname()


settings = Settings()
if not settings.session_secret:
    raise RuntimeError("SESSION_SECRET es obligatorio")
