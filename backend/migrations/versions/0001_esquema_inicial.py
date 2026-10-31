"""Esquema inicial de RedAlimenta

Revision ID: 0001
Revises:
"""
import os

from alembic import op

revision = "0001"
down_revision = None

APP = os.getenv("APP_DB_ROLE", "redalimenta_app")
RO = os.getenv("READONLY_DB_ROLE", "redalimenta_backup")


def upgrade():
    op.execute("""
    CREATE TABLE usuarios (
      id serial PRIMARY KEY,
      email varchar(120) NOT NULL UNIQUE,
      nombre varchar(120) NOT NULL,
      password_hash varchar(255) NOT NULL,
      rol varchar(20) NOT NULL CHECK (rol IN ('admin','coordinador','trabajador_social','voluntario')),
      ruta varchar(30),
      activo boolean NOT NULL DEFAULT true,
      creado_en timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_voluntario_ruta CHECK (rol <> 'voluntario' OR ruta IS NOT NULL)
    );
    CREATE TABLE donantes (
      id serial PRIMARY KEY,
      nombre varchar(120) NOT NULL UNIQUE,
      tipo varchar(20) NOT NULL CHECK (tipo IN ('supermercado','productor','particular')),
      contacto varchar(120),
      activo boolean NOT NULL DEFAULT true,
      creado_en timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE productos (
      id serial PRIMARY KEY,
      nombre varchar(120) NOT NULL UNIQUE,
      categoria varchar(30) NOT NULL CHECK (categoria IN ('refrigerado','enlatado','fruta_verdura','granos','panaderia','otros')),
      refrigerado boolean NOT NULL DEFAULT false,
      alergenos text[] NOT NULL DEFAULT '{}',
      peso_unitario_kg numeric(8,3) NOT NULL CHECK (peso_unitario_kg > 0),
      unidades_por_racion numeric(5,2) NOT NULL DEFAULT 0 CHECK (unidades_por_racion >= 0),
      activo boolean NOT NULL DEFAULT true
    );
    CREATE SEQUENCE folio_lote_seq START 1000;
    CREATE SEQUENCE folio_despensa_seq START 1000;
    CREATE TABLE lotes (
      id serial PRIMARY KEY,
      folio varchar(30) NOT NULL UNIQUE,
      producto_id integer NOT NULL REFERENCES productos(id),
      donante_id integer NOT NULL REFERENCES donantes(id),
      cantidad_inicial integer NOT NULL CHECK (cantidad_inicial > 0),
      cantidad_disponible integer NOT NULL,
      fecha_recepcion date NOT NULL DEFAULT current_date,
      fecha_caducidad date NOT NULL,
      estado varchar(20) NOT NULL DEFAULT 'recibido' CHECK (estado IN ('recibido','en_inspeccion','disponible',
             'rechazado','prioritario','asignado','entregado','merma','retirado')),
      temperatura_c numeric(4,1),
      motivo varchar(255),
      creado_por integer REFERENCES usuarios(id),
      creado_en timestamptz NOT NULL DEFAULT now(),
      actualizado_en timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT ck_lote_cantidad CHECK (cantidad_disponible >= 0 AND cantidad_disponible <= cantidad_inicial),
      CONSTRAINT ck_lote_fechas CHECK (fecha_caducidad >= fecha_recepcion)
    );
    CREATE INDEX ix_lotes_estado_caducidad ON lotes (estado, fecha_caducidad);
    CREATE INDEX ix_lotes_producto_fefo ON lotes (producto_id, fecha_caducidad) WHERE estado IN ('disponible','prioritario');
    CREATE TABLE hogares (
      id serial PRIMARY KEY,
      clave varchar(20) NOT NULL UNIQUE,
      responsable varchar(120) NOT NULL,
      integrantes smallint NOT NULL CHECK (integrantes BETWEEN 1 AND 20),
      alergenos text[] NOT NULL DEFAULT '{}',
      colonia varchar(120) NOT NULL,
      ruta varchar(30) NOT NULL,
      telefono varchar(20),
      ultima_entrega date,
      activo boolean NOT NULL DEFAULT true,
      creado_en timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_hogares_ultima_entrega ON hogares (id, ultima_entrega);
    CREATE INDEX ix_hogares_ruta ON hogares (ruta);
    CREATE TABLE despensas (
      id serial PRIMARY KEY,
      folio varchar(30) NOT NULL UNIQUE,
      hogar_id integer NOT NULL REFERENCES hogares(id),
      estado varchar(20) NOT NULL CHECK (estado IN ('solicitada','aprobada','en_preparacion','lista','entregada',
             'rechazada','cancelada','no_recogida')),
      raciones numeric(3,1) NOT NULL CHECK (raciones BETWEEN 1 AND 4),
      fecha_programada date NOT NULL,
      solicitada_por integer REFERENCES usuarios(id),
      aprobada_por integer REFERENCES usuarios(id),
      preparada_por integer REFERENCES usuarios(id),
      entregada_por integer REFERENCES usuarios(id),
      motivo_cierre varchar(255),
      lista_en timestamptz,
      entregada_en timestamptz,
      creado_en timestamptz NOT NULL DEFAULT now(),
      actualizado_en timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_despensas_hogar_estado ON despensas (hogar_id, estado);
    CREATE INDEX ix_despensas_entregada_en ON despensas (entregada_en) WHERE estado = 'entregada';
    -- Un hogar no puede tener dos despensas en curso (apoya la regla de frecuencia)
    CREATE UNIQUE INDEX ux_despensa_abierta_por_hogar ON despensas (hogar_id)
      WHERE estado IN ('solicitada','aprobada','en_preparacion','lista');
    CREATE TABLE despensa_detalle (
      id serial PRIMARY KEY,
      despensa_id integer NOT NULL REFERENCES despensas(id) ON DELETE CASCADE,
      lote_id integer NOT NULL REFERENCES lotes(id),
      cantidad integer NOT NULL CHECK (cantidad > 0),
      CONSTRAINT ux_detalle UNIQUE (despensa_id, lote_id)
    );
    CREATE INDEX ix_detalle_lote ON despensa_detalle (lote_id);
    CREATE TABLE outbox (
      id bigserial PRIMARY KEY,
      event_id uuid NOT NULL UNIQUE DEFAULT gen_random_uuid(),
      tipo varchar(40) NOT NULL,
      lote_id integer,
      payload jsonb NOT NULL,
      creado_en timestamptz NOT NULL DEFAULT now(),
      publicado_en timestamptz,
      intentos integer NOT NULL DEFAULT 0,
      ultimo_error text
    );
    CREATE INDEX ix_outbox_pendientes ON outbox (id) WHERE publicado_en IS NULL;
    CREATE TABLE login_intentos (
      id bigserial PRIMARY KEY,
      email varchar(120) NOT NULL,
      ip varchar(64) NOT NULL,
      exito boolean NOT NULL,
      ts timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_login_email_ts ON login_intentos (email, ts);
    """)
    # Mínimo privilegio: la cuenta de ejecución solo hace DML; no puede crear ni borrar tablas.
    op.execute(f"""
    GRANT USAGE ON SCHEMA public TO {APP};
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP};
    GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO {APP};
    REVOKE DELETE ON outbox, login_intentos FROM {APP};
    GRANT USAGE ON SCHEMA public TO {RO};
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO {RO};
    GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO {RO};
    """)


def downgrade():
    op.execute("""DROP TABLE IF EXISTS login_intentos, outbox, despensa_detalle, despensas, hogares, lotes,
                  productos, donantes, usuarios CASCADE; DROP SEQUENCE IF EXISTS folio_lote_seq, folio_despensa_seq;""")
