"""Validación de servidor: tipos, obligatorios, rangos y listas cerradas."""
from datetime import date
from decimal import Decimal
from typing import Literal, Any

from typing import Annotated

from pydantic import BaseModel, Field, field_validator, ConfigDict, StringConstraints

from .models import ALERGENOS

# Correo validado por patrón (los usuarios de prueba usan el dominio reservado .test)
EmailStr = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=120,
                                            pattern=r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")]
Rol = Literal["admin", "coordinador", "trabajador_social", "voluntario"]
Categoria = Literal["refrigerado", "enlatado", "fruta_verdura", "granos", "panaderia", "otros"]
TipoDonante = Literal["supermercado", "productor", "particular"]


def _alergenos(v: list[str]) -> list[str]:
    v = sorted(set(a.strip().lower() for a in v))
    malos = [a for a in v if a not in ALERGENOS]
    if malos:
        raise ValueError(f"Alérgenos no reconocidos: {', '.join(malos)}")
    return v


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UsuarioIn(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=3, max_length=120)
    rol: Rol
    ruta: str | None = Field(default=None, max_length=30)
    password: str | None = Field(default=None, min_length=10, max_length=200)
    activo: bool = True


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    nombre: str
    rol: str
    ruta: str | None
    activo: bool


class DonanteIn(BaseModel):
    nombre: str = Field(min_length=3, max_length=120)
    tipo: TipoDonante
    contacto: str | None = Field(default=None, max_length=120)
    activo: bool = True


class DonanteOut(DonanteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    categoria: Categoria
    refrigerado: bool = False
    alergenos: list[str] = []
    peso_unitario_kg: Decimal = Field(gt=0, le=100)
    unidades_por_racion: Decimal = Field(ge=0, le=20)
    activo: bool = True
    _v = field_validator("alergenos")(_alergenos)


class ProductoOut(ProductoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class LoteIn(BaseModel):
    producto_id: int = Field(gt=0)
    donante_id: int = Field(gt=0)
    cantidad_inicial: int = Field(gt=0, le=100000)
    fecha_caducidad: date


class LoteUpdate(BaseModel):
    cantidad_inicial: int | None = Field(default=None, gt=0, le=100000)
    fecha_caducidad: date | None = None
    donante_id: int | None = Field(default=None, gt=0)


class InspeccionIn(BaseModel):
    temperatura_c: Decimal | None = Field(default=None, ge=-30, le=60)
    checklist: dict[str, Any] = Field(default_factory=dict)
    aprobado: bool = True
    observaciones: str | None = Field(default=None, max_length=500)


class LoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    folio: str
    producto_id: int
    producto_nombre: str
    categoria: str
    donante_id: int
    donante_nombre: str
    cantidad_inicial: int
    cantidad_disponible: int
    fecha_recepcion: date
    fecha_caducidad: date
    estado: str
    temperatura_c: Decimal | None
    motivo: str | None


class HogarIn(BaseModel):
    clave: str = Field(min_length=3, max_length=20, pattern=r"^[A-Z0-9-]+$")
    responsable: str = Field(min_length=3, max_length=120)
    integrantes: int = Field(ge=1, le=20)
    alergenos: list[str] = []
    colonia: str = Field(min_length=2, max_length=120)
    ruta: str = Field(min_length=1, max_length=30)
    telefono: str | None = Field(default=None, pattern=r"^[0-9 +-]{7,20}$")
    activo: bool = True
    _v = field_validator("alergenos")(_alergenos)


class HogarOut(HogarIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ultima_entrega: date | None
    clave: str


class DespensaIn(BaseModel):
    hogar_id: int = Field(gt=0)
    fecha_programada: date


class TransicionIn(BaseModel):
    motivo: str | None = Field(default=None, max_length=255)


class ItemManualIn(BaseModel):
    lote_id: int = Field(gt=0)
    cantidad: int = Field(gt=0, le=1000)


class RetiroIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=255)


class Pagina(BaseModel):
    total: int
    page: int
    size: int
    items: list[Any]
