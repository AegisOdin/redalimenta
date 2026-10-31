import os

from alembic import context
from sqlalchemy import create_engine

# La migración usa la cuenta de migración (dueña del esquema), distinta de la cuenta de ejecución.
url = os.environ["MIGRATION_DATABASE_URL"]


def run():
    engine = create_engine(url)
    with engine.connect() as conn:
        # Bloqueo consultivo: aunque se lancen dos Jobs, solo uno migra a la vez
        conn.exec_driver_sql("SELECT pg_advisory_lock(727274)")
        context.configure(connection=conn, target_metadata=None, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
        conn.exec_driver_sql("SELECT pg_advisory_unlock(727274)")
        conn.commit()


run()
