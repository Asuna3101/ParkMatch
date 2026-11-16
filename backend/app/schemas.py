"""Esquemas de entrada y salida de la API (Pydantic)."""
import re
from datetime import datetime, time
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .tarifas import a_minutos, hay_solape


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- usuarios
def _contrasena_segura(v: str) -> str:
    if not re.search(r"[A-Za-z]", v) or not re.search(r"\d", v):
        raise ValueError("La contraseña debe combinar letras y números.")
    return v


class RegistroEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    correo: EmailStr
    contrasena: str = Field(min_length=8, max_length=72)
    telefono: Optional[str] = Field(default=None, max_length=20)
    rol: Literal["arrendador", "arrendatario"]
    # Consentimiento para el tratamiento de datos personales (Ley N.º 29733)
    acepta_datos: bool = False

    @field_validator("acepta_datos")
    @classmethod
    def consentimiento(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Para crear tu cuenta debes aceptar el tratamiento de tus datos personales.")
        return v

    @field_validator("nombre")
    @classmethod
    def nombre_limpio(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Escribe tu nombre completo.")
        return v

    @field_validator("contrasena")
    @classmethod
    def contrasena_segura(cls, v: str) -> str:
        return _contrasena_segura(v)


class LoginEntrada(BaseModel):
    correo: EmailStr
    contrasena: str


class UsuarioSalida(Base):
    id: int
    nombre: str
    correo: EmailStr
    telefono: Optional[str] = None
    rol: str
    foto_url: Optional[str] = None
    verificacion: str = "sin_verificar"


class RecuperarEntrada(BaseModel):
    correo: EmailStr


class RecuperarSalida(BaseModel):
    mensaje: str
    enlace_demo: Optional[str] = None     # solo en modo demostración


class RestablecerEntrada(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    contrasena: str = Field(min_length=8, max_length=72)

    _segura = field_validator("contrasena")(classmethod(lambda cls, v: _contrasena_segura(v)))


class CambiarContrasenaEntrada(BaseModel):
    actual: str
    nueva: str = Field(min_length=8, max_length=72)

    _segura = field_validator("nueva")(classmethod(lambda cls, v: _contrasena_segura(v)))


class PerfilEntrada(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    telefono: Optional[str] = Field(default=None, max_length=20)

    @field_validator("nombre")
    @classmethod
    def nombre_limpio(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Escribe tu nombre completo.")
        return v


class VehiculoEntrada(BaseModel):
    placa: str = Field(min_length=5, max_length=10)
    tipo: Literal["moto", "auto", "camioneta"]
    descripcion: Optional[str] = Field(default=None, max_length=80)

    @field_validator("placa")
    @classmethod
    def placa_limpia(cls, v: str) -> str:
        v = v.strip().upper().replace(" ", "")
        if not re.fullmatch(r"[A-Z0-9-]{5,10}", v):
            raise ValueError("Escribe la placa con letras y números, por ejemplo ABC-123.")
        return v


class VehiculoSalida(Base):
    id: int
    placa: str
    tipo: str
    descripcion: Optional[str] = None


class PerfilSalida(UsuarioSalida):
    tiene_documento: bool = False
    creado_en: datetime
    vehiculos: List[VehiculoSalida] = []


class ResenaSalida(BaseModel):
    id: int
    autor_id: int
    autor_nombre: str
    autor_foto: Optional[str] = None
    estrellas: int
    comentario: Optional[str] = None
    cochera_titulo: Optional[str] = None
    creado_en: datetime


class PerfilPublico(BaseModel):
    """Lo que cualquiera puede ver de otra persona (US-21)."""
    id: int
    nombre: str
    rol: str
    foto_url: Optional[str] = None
    verificado: bool
    miembro_desde: datetime
    calificacion_promedio: Optional[float] = None
    total_calificaciones: int = 0
    transacciones_completadas: int = 0
    resenas: List[ResenaSalida] = []
    cocheras: List["CocheraResumen"] = []


class SesionSalida(BaseModel):
    token: str
    usuario: UsuarioSalida


# ---------------------------------------------------------------- cocheras
class FranjaTarifa(Base):
    hora_inicio: time
    hora_fin: time
    precio_hora: float = Field(gt=0, le=999)

    @model_validator(mode="after")
    def orden(self):
        if a_minutos(self.hora_fin) <= a_minutos(self.hora_inicio):
            raise ValueError("En cada tarifa, la hora final debe ser posterior a la inicial.")
        return self


class FranjaDisponible(Base):
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fin: time

    @model_validator(mode="after")
    def orden(self):
        if a_minutos(self.hora_fin) <= a_minutos(self.hora_inicio):
            raise ValueError("En el calendario, la hora final debe ser posterior a la inicial.")
        return self


def _sin_solapes_tarifa(tarifas: List[FranjaTarifa]) -> None:
    if hay_solape((a_minutos(t.hora_inicio), a_minutos(t.hora_fin)) for t in tarifas):
        raise ValueError("Dos tarifas se cruzan en el mismo horario.")


def _sin_solapes_calendario(franjas: List[FranjaDisponible]) -> None:
    for dia in range(7):
        del_dia = [(a_minutos(f.hora_inicio), a_minutos(f.hora_fin))
                   for f in franjas if f.dia_semana == dia]
        if hay_solape(del_dia):
            raise ValueError("Dos franjas del calendario se cruzan el mismo día.")


class TarifasEntrada(BaseModel):
    precio_hora: Decimal = Field(gt=0, le=999)
    tarifas: List[FranjaTarifa] = []

    @model_validator(mode="after")
    def validar(self):
        _sin_solapes_tarifa(self.tarifas)
        return self


class DisponibilidadEntrada(BaseModel):
    franjas: List[FranjaDisponible] = Field(min_length=1)

    @model_validator(mode="after")
    def validar(self):
        _sin_solapes_calendario(self.franjas)
        return self


class CocheraEntrada(BaseModel):
    titulo: str = Field(min_length=5, max_length=120)
    descripcion: str = Field(min_length=20, max_length=2000)
    tipo_vehiculo: Literal["moto", "auto", "camioneta"]
    largo_m: Decimal = Field(gt=0, le=20)
    ancho_m: Decimal = Field(gt=0, le=10)
    techada: bool = False
    precio_hora: Decimal = Field(gt=0, le=999)
    direccion: str = Field(min_length=5, max_length=200)
    distrito: str = Field(min_length=2, max_length=80)
    referencia: Optional[str] = Field(default=None, max_length=200)
    latitud: Decimal = Field(ge=-90, le=90)
    longitud: Decimal = Field(ge=-180, le=180)
    tarifas: List[FranjaTarifa] = []
    disponibilidad: List[FranjaDisponible] = Field(min_length=1)

    @model_validator(mode="after")
    def validar(self):
        _sin_solapes_tarifa(self.tarifas)
        _sin_solapes_calendario(self.disponibilidad)
        return self


class CocheraEdicion(BaseModel):
    """Datos del anuncio que el arrendador puede corregir después (requisito 7)."""
    titulo: str = Field(min_length=5, max_length=120)
    descripcion: str = Field(min_length=20, max_length=2000)
    tipo_vehiculo: Literal["moto", "auto", "camioneta"]
    largo_m: Decimal = Field(gt=0, le=20)
    ancho_m: Decimal = Field(gt=0, le=10)
    techada: bool = False
    direccion: str = Field(min_length=5, max_length=200)
    distrito: str = Field(min_length=2, max_length=80)
    referencia: Optional[str] = Field(default=None, max_length=200)
    latitud: Decimal = Field(ge=-90, le=90)
    longitud: Decimal = Field(ge=-180, le=180)


class EstadoEntrada(BaseModel):
    activa: bool


class UbicacionSalida(Base):
    direccion: str
    distrito: str
    referencia: Optional[str] = None
    latitud: float
    longitud: float


class CocheraResumen(BaseModel):
    """Lo que necesita el mapa y los listados."""
    id: int
    titulo: str
    tipo_vehiculo: str
    techada: bool
    precio_hora: float
    activa: bool
    direccion: str
    distrito: str
    latitud: float
    longitud: float
    foto: Optional[str] = None
    distancia_km: Optional[float] = None
    suspendida: bool = False
    calificacion: Optional[float] = None      # promedio de estrellas de la cochera
    total_calificaciones: int = 0
    costo_horario: Optional[float] = None     # costo del horario buscado, si se indicó


class FotoSalida(Base):
    id: int
    url: str


class Ocupado(BaseModel):
    inicio: datetime
    fin: datetime


class CocheraDetalle(BaseModel):
    id: int
    titulo: str
    descripcion: str
    tipo_vehiculo: str
    largo_m: float
    ancho_m: float
    techada: bool
    precio_hora: float
    activa: bool
    suspendida: bool = False
    motivo_suspension: Optional[str] = None
    arrendador_id: int
    arrendador_nombre: str
    arrendador_foto: Optional[str] = None
    arrendador_verificado: bool = False
    arrendador_telefono: Optional[str] = None   # solo para quien inició sesión
    ubicacion: UbicacionSalida
    fotos: List[str]
    fotos_detalle: List[FotoSalida] = []
    tarifas: List[FranjaTarifa]
    disponibilidad: List[FranjaDisponible]
    ocupado: List[Ocupado] = []
    calificacion: Optional[float] = None
    total_calificaciones: int = 0
    resenas: List[ResenaSalida] = []


class Cotizacion(BaseModel):
    disponible: bool
    motivo: Optional[str] = None
    minutos: int = 0
    costo_total: float = 0


# ---------------------------------------------------------------- reservas
class ReservaEntrada(BaseModel):
    cochera_id: int
    inicio: datetime
    fin: datetime
    medio_pago: Literal["tarjeta", "acordado"] = "acordado"
    metodo_pago_id: Optional[int] = None

    @model_validator(mode="after")
    def tarjeta_elegida(self):
        if self.medio_pago == "tarjeta" and self.metodo_pago_id is None:
            raise ValueError("Elige la tarjeta con la que vas a pagar.")
        return self


class MedioPagoEntrada(BaseModel):
    """Cambio del medio de pago de una solicitud aún no confirmada."""
    medio_pago: Literal["tarjeta", "acordado"]
    metodo_pago_id: Optional[int] = None

    @model_validator(mode="after")
    def tarjeta_elegida(self):
        if self.medio_pago == "tarjeta" and self.metodo_pago_id is None:
            raise ValueError("Elige la tarjeta con la que vas a pagar.")
        return self


class RechazoEntrada(BaseModel):
    motivo: Optional[str] = Field(default=None, max_length=200)


class PagoSalida(BaseModel):
    id: int
    monto: float
    estado: str
    medio: Optional[str] = None
    referencia: Optional[str] = None
    pagado_en: Optional[datetime] = None
    reembolsado_en: Optional[datetime] = None
    comprobante_id: Optional[int] = None
    comprobante_numero: Optional[str] = None


class CodigoSalida(BaseModel):
    codigo: str
    valido_desde: datetime
    valido_hasta: datetime
    usado_en: Optional[datetime] = None
    enlace: str                                # lo que contiene el QR


class ReservaSalida(BaseModel):
    id: int
    cochera_id: int
    cochera_titulo: str
    cochera_direccion: str
    cochera_foto: Optional[str] = None
    arrendador_id: int
    arrendador_nombre: str
    arrendatario_id: int
    arrendatario_nombre: str
    arrendatario_verificado: bool = False
    otro_telefono: Optional[str] = None        # contacto de la otra parte, si hay reserva vigente
    inicio: datetime
    fin: datetime
    estado: str
    costo_total: float
    motivo_rechazo: Optional[str] = None
    medio_pago: str = "acordado"
    tarjeta: Optional[str] = None              # "Visa •••• 4242"
    ingreso_real: Optional[datetime] = None
    salida_real: Optional[datetime] = None
    minutos_exceso: int = 0
    cargo_exceso: float = 0
    penalizacion: float = 0
    total_final: float = 0                     # costo + tiempo adicional + penalización
    creado_en: datetime
    pago: Optional[PagoSalida] = None
    codigo: Optional[CodigoSalida] = None      # solo lo ve el arrendatario
    conversacion_id: Optional[int] = None
    puede_cancelar: bool = False
    devolucion_si_cancela: bool = False        # ¿aún está dentro del plazo con devolución?
    puede_calificar: bool = False
    mi_calificacion: Optional[int] = None
    disputa_abierta: bool = False


class PagoRecibidoEntrada(BaseModel):
    medio: Literal["efectivo", "billetera"]


class ValidarCodigoEntrada(BaseModel):
    codigo: str = Field(min_length=4, max_length=12)

    @field_validator("codigo")
    @classmethod
    def limpio(cls, v: str) -> str:
        return v.strip().upper().replace(" ", "").replace("-", "")


class TarjetaEntrada(BaseModel):
    """Tarjeta simulada (US-26). El CVV se valida y se descarta: no se guarda."""
    titular: str = Field(min_length=3, max_length=80)
    numero: str = Field(min_length=13, max_length=23)
    vence_mes: int = Field(ge=1, le=12)
    vence_anio: int = Field(ge=2024, le=2099)
    cvv: str = Field(min_length=3, max_length=4)


class TarjetaEdicion(BaseModel):
    titular: str = Field(min_length=3, max_length=80)
    vence_mes: int = Field(ge=1, le=12)
    vence_anio: int = Field(ge=2024, le=2099)


class TarjetaSalida(Base):
    id: int
    titular: str
    marca: str
    ultimos4: str
    vence_mes: int
    vence_anio: int


class ComprobanteSalida(BaseModel):
    id: int
    numero: str
    emitido_en: datetime
    monto: float
    medio: str
    referencia: Optional[str] = None
    estado_pago: str
    reserva_id: int
    cochera_titulo: str
    cochera_direccion: str
    inicio: datetime
    fin: datetime
    arrendador_nombre: str
    arrendatario_nombre: str


class PagoArrendador(BaseModel):
    """Fila del estado de pagos del arrendador (US-30)."""
    reserva_id: int
    cochera_id: int
    cochera_titulo: str
    arrendatario_nombre: str
    inicio: datetime
    fin: datetime
    estado_reserva: str
    monto: float
    estado: str
    medio: Optional[str] = None
    pagado_en: Optional[datetime] = None
    reembolsado_en: Optional[datetime] = None
    comprobante_id: Optional[int] = None
    comprobante_numero: Optional[str] = None


class ResumenPagos(BaseModel):
    pagos: List[PagoArrendador]
    total_pagado: float
    total_pendiente: float
    total_reembolsado: float


class AuditoriaSalida(BaseModel):
    id: int
    accion: str
    entidad: str
    entidad_id: Optional[int] = None
    usuario_nombre: Optional[str] = None
    detalle: dict
    creado_en: datetime


# ------------------------------------------------------------ calificaciones
class CalificacionEntrada(BaseModel):
    estrellas: int = Field(ge=1, le=5)
    comentario: Optional[str] = Field(default=None, max_length=600)


# ------------------------------------------------------------ notificaciones
class NotificacionSalida(Base):
    id: int
    tipo: str
    titulo: str
    texto: str
    enlace: Optional[str] = None
    leida: bool
    creado_en: datetime


class BandejaNotificaciones(BaseModel):
    sin_leer: int
    notificaciones: List[NotificacionSalida]


# ------------------------------------------------- moderación y disputas
MOTIVOS_REPORTE = Literal["informacion_falsa", "fotos_enganosas", "precio_abusivo",
                          "inseguro", "contenido_inapropiado", "otro"]


class ReporteEntrada(BaseModel):
    motivo: MOTIVOS_REPORTE
    detalle: Optional[str] = Field(default=None, max_length=600)


class ReporteSalida(BaseModel):
    id: int
    cochera_id: int
    cochera_titulo: str
    cochera_foto: Optional[str] = None
    cochera_suspendida: bool
    arrendador_id: int
    arrendador_nombre: str
    autor_id: int
    autor_nombre: str
    motivo: str
    detalle: Optional[str] = None
    estado: str
    nota: Optional[str] = None
    creado_en: datetime
    resuelto_en: Optional[datetime] = None
    reportes_previos: int = 0                  # otros reportes de la misma cochera


class ResolverReporteEntrada(BaseModel):
    decision: Literal["procedente", "desestimado"]
    nota: Optional[str] = Field(default=None, max_length=300)


class DisputaEntrada(BaseModel):
    tipo: Literal["reserva", "pago", "conducta"]
    descripcion: str = Field(min_length=15, max_length=1500)


class DisputaSalida(BaseModel):
    id: int
    reserva_id: int
    cochera_titulo: str
    autor_id: int
    autor_nombre: str
    arrendador_id: int
    arrendador_nombre: str
    arrendatario_id: int
    arrendatario_nombre: str
    tipo: str
    descripcion: str
    estado: str
    resolucion: Optional[str] = None
    creado_en: datetime
    resuelto_en: Optional[datetime] = None
    # contexto para quien resuelve
    inicio: Optional[datetime] = None
    fin: Optional[datetime] = None
    estado_reserva: Optional[str] = None
    monto: Optional[float] = None
    estado_pago: Optional[str] = None


class ResolverDisputaEntrada(BaseModel):
    accion: Literal["reembolso", "cancelacion", "sin_accion"]
    resolucion: str = Field(min_length=10, max_length=1500)


class VerificacionSalida(BaseModel):
    usuario_id: int
    nombre: str
    correo: str
    rol: str
    verificacion: str
    creado_en: datetime


class ResolverVerificacionEntrada(BaseModel):
    aprobar: bool


class ResumenAdmin(BaseModel):
    usuarios: int
    cocheras_activas: int
    cocheras_suspendidas: int
    reservas: int
    reportes_pendientes: int
    disputas_abiertas: int
    verificaciones_pendientes: int


# -------------------------------------------------------------------- chat
class ConversacionEntrada(BaseModel):
    cochera_id: int


class MensajeEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=1000)

    @field_validator("texto")
    @classmethod
    def no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Escribe un mensaje.")
        return v


class MensajeSalida(Base):
    id: int
    conversacion_id: int
    emisor_id: int
    texto: str
    leido: bool
    enviado_en: datetime


class ConversacionSalida(BaseModel):
    id: int
    cochera_id: int
    cochera_titulo: str
    otro_id: int
    otro_nombre: str
    otro_foto: Optional[str] = None
    ultimo_mensaje: Optional[str] = None
    ultimo_en: Optional[datetime] = None
    sin_leer: int = 0


PerfilPublico.model_rebuild()
