"""Índice para reproyección del outbox por fecha (cambio compatible hacia atrás).

Revision ID: 0002
Revises: 0001
Plan de reversión: la versión 1.0.0 de la imagen funciona con este índice presente; downgrade solo lo elimina.
"""
from alembic import op

revision = "0002"
down_revision = "0001"


def upgrade():
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_creado_en ON outbox (creado_en)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_outbox_creado_en")
