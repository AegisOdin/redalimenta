"""Modelos ORM. El DDL autoritativo está en migrations/ (Alembic); estos modelos lo reflejan."""
from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import (Boolean, Date, DateTime, ForeignKey, Integer, BigInteger, Numeric,
                        SmallInteger, String, Text, func)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

ROLES = ("admin", "coordinador", "trabajador_social", "voluntario")
ESTADOS_LOTE = ("recibido", "en_inspeccion", "disponible", "rechazado", "prioritario",
                "asignado", "entregado", "merma", "retirado")
ESTADOS_DESPENSA = ("solicitada", "aprobada", "en_preparacion", "lista", "entregada",
                    "rechazada", "cancelada", "no_recogida")
CATEGORIAS = ("refrigerado", "enlatado", "fruta_verdura", "granos", "panaderia", "otros")
ALERGENOS = ("gluten", "lacteos", "cacahuate", "huevo", "soya", "mariscos", "nueces")


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    ruta: Mapped[str | None] = mapped_column(String(30))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Donante(Base):
    __tablename__ = "donantes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))
    contacto: Mapped[str | None] = mapped_column(String(120))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Producto(Base):
    __tablename__ = "productos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    categoria: Mapped[str] = mapped_column(String(30))
    refrigerado: Mapped[bool] = mapped_column(Boolean, default=False)
    alergenos: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    peso_unitario_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    unidades_por_racion: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Lote(Base):
    __tablename__ = "lotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    donante_id: Mapped[int] = mapped_column(ForeignKey("donantes.id"))
    cantidad_inicial: Mapped[int] = mapped_column(Integer)
    cantidad_disponible: Mapped[int] = mapped_column(Integer)
    fecha_recepcion: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    fecha_caducidad: Mapped[date] = mapped_column(Date)
    estado: Mapped[str] = mapped_column(String(20), default="recibido")
    temperatura_c: Mapped[Decimal | None] = mapped_column(Numeric(4, 1))
    motivo: Mapped[str | None] = mapped_column(String(255))
    creado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    producto: Mapped[Producto] = relationship(lazy="joined")
    donante: Mapped[Donante] = relationship(lazy="joined")


class Hogar(Base):
    __tablename__ = "hogares"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clave: Mapped[str] = mapped_column(String(20), unique=True)
    responsable: Mapped[str] = mapped_column(String(120))
    integrantes: Mapped[int] = mapped_column(SmallInteger)
    alergenos: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    colonia: Mapped[str] = mapped_column(String(120))
    ruta: Mapped[str] = mapped_column(String(30))
    telefono: Mapped[str | None] = mapped_column(String(20))
    ultima_entrega: Mapped[date | None] = mapped_column(Date)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Despensa(Base):
    __tablename__ = "despensas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    folio: Mapped[str] = mapped_column(String(30), unique=True)
    hogar_id: Mapped[int] = mapped_column(ForeignKey("hogares.id"))
    estado: Mapped[str] = mapped_column(String(20), default="solicitada")
    raciones: Mapped[Decimal] = mapped_column(Numeric(3, 1))
    fecha_programada: Mapped[date] = mapped_column(Date)
    solicitada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    aprobada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    preparada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    entregada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_cierre: Mapped[str | None] = mapped_column(String(255))
    lista_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    entregada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    hogar: Mapped[Hogar] = relationship(lazy="joined")
    detalle: Mapped[list["DespensaDetalle"]] = relationship(back_populates="despensa", cascade="all, delete-orphan")


class DespensaDetalle(Base):
    __tablename__ = "despensa_detalle"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    despensa_id: Mapped[int] = mapped_column(ForeignKey("despensas.id", ondelete="CASCADE"))
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id"))
    cantidad: Mapped[int] = mapped_column(Integer)
    despensa: Mapped[Despensa] = relationship(back_populates="detalle")
    lote: Mapped[Lote] = relationship(lazy="joined")


class Outbox(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    tipo: Mapped[str] = mapped_column(String(40))
    lote_id: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    publicado_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_error: Mapped[str | None] = mapped_column(Text)


class LoginIntento(Base):
    __tablename__ = "login_intentos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(120))
    ip: Mapped[str] = mapped_column(String(64))
    exito: Mapped[bool] = mapped_column(Boolean)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
