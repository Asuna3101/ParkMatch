"""Modelos ORM. Reflejan las tablas definidas en db/schema.sql."""
from datetime import datetime, time
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger,
    String, Text, Time, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(160), unique=True)
    contrasena_hash: Mapped[str] = mapped_column(String(100))
    telefono: Mapped[Optional[str]] = mapped_column(String(20))
    rol: Mapped[str] = mapped_column(String(20))
    foto_url: Mapped[Optional[str]] = mapped_column(String(255))
    documento_url: Mapped[Optional[str]] = mapped_column(String(255))
    verificacion: Mapped[str] = mapped_column(String(20), default="sin_verificar")
    acepto_datos_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vehiculos: Mapped[List["Vehiculo"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan", order_by="Vehiculo.id")


class Vehiculo(Base):
    __tablename__ = "vehiculo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    placa: Mapped[str] = mapped_column(String(10))
    tipo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[Optional[str]] = mapped_column(String(80))

    usuario: Mapped[Usuario] = relationship(back_populates="vehiculos")


class RecuperacionContrasena(Base):
    __tablename__ = "recuperacion_contrasena"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MetodoPago(Base):
    """Tarjeta simulada del arrendatario. El número va cifrado; el CVV no se guarda."""
    __tablename__ = "metodo_pago"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    titular: Mapped[str] = mapped_column(String(80))
    marca: Mapped[str] = mapped_column(String(20))
    ultimos4: Mapped[str] = mapped_column(String(4))
    vence_mes: Mapped[int] = mapped_column(SmallInteger)
    vence_anio: Mapped[int] = mapped_column(SmallInteger)
    numero_cifrado: Mapped[str] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Cochera(Base):
    __tablename__ = "cochera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    arrendador_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    titulo: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(Text)
    tipo_vehiculo: Mapped[str] = mapped_column(String(20))
    largo_m: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    ancho_m: Mapped[Decimal] = mapped_column(Numeric(4, 2))
    techada: Mapped[bool] = mapped_column(Boolean, default=False)
    precio_hora: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    suspendida: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_suspension: Mapped[Optional[str]] = mapped_column(String(300))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    arrendador: Mapped[Usuario] = relationship()
    ubicacion: Mapped["Ubicacion"] = relationship(
        back_populates="cochera", uselist=False, cascade="all, delete-orphan")
    fotos: Mapped[List["FotoCochera"]] = relationship(
        back_populates="cochera", cascade="all, delete-orphan", order_by="FotoCochera.orden")
    tarifas: Mapped[List["Tarifa"]] = relationship(
        back_populates="cochera", cascade="all, delete-orphan", order_by="Tarifa.hora_inicio")
    disponibilidades: Mapped[List["Disponibilidad"]] = relationship(
        back_populates="cochera", cascade="all, delete-orphan",
        order_by="Disponibilidad.dia_semana, Disponibilidad.hora_inicio")


class Ubicacion(Base):
    __tablename__ = "ubicacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"), unique=True)
    direccion: Mapped[str] = mapped_column(String(200))
    distrito: Mapped[str] = mapped_column(String(80))
    referencia: Mapped[Optional[str]] = mapped_column(String(200))
    latitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitud: Mapped[Decimal] = mapped_column(Numeric(9, 6))

    cochera: Mapped[Cochera] = relationship(back_populates="ubicacion")


class FotoCochera(Base):
    __tablename__ = "foto_cochera"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(String(255))
    orden: Mapped[int] = mapped_column(SmallInteger, default=0)

    cochera: Mapped[Cochera] = relationship(back_populates="fotos")


class Tarifa(Base):
    __tablename__ = "tarifa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    precio_hora: Mapped[Decimal] = mapped_column(Numeric(8, 2))

    cochera: Mapped[Cochera] = relationship(back_populates="tarifas")


class Disponibilidad(Base):
    __tablename__ = "disponibilidad"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    dia_semana: Mapped[int] = mapped_column(SmallInteger)  # 0 = lunes … 6 = domingo
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)

    cochera: Mapped[Cochera] = relationship(back_populates="disponibilidades")


class Reserva(Base):
    __tablename__ = "reserva"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    arrendatario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estado: Mapped[str] = mapped_column(String(20), default="solicitada")
    costo_total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    motivo_rechazo: Mapped[Optional[str]] = mapped_column(String(200))
    medio_pago: Mapped[str] = mapped_column(String(20), default="acordado")
    metodo_pago_id: Mapped[Optional[int]] = mapped_column(ForeignKey("metodo_pago.id", ondelete="SET NULL"))
    ingreso_real: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    salida_real: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    minutos_exceso: Mapped[int] = mapped_column(Integer, default=0)
    cargo_exceso: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    penalizacion: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    cochera: Mapped[Cochera] = relationship()
    arrendatario: Mapped[Usuario] = relationship()
    metodo_pago: Mapped[Optional[MetodoPago]] = relationship()
    pago: Mapped[Optional["Pago"]] = relationship(
        back_populates="reserva", uselist=False, cascade="all, delete-orphan")
    codigo: Mapped[Optional["CodigoAcceso"]] = relationship(
        back_populates="reserva", uselist=False, cascade="all, delete-orphan")
    calificaciones: Mapped[List["Calificacion"]] = relationship(
        back_populates="reserva", cascade="all, delete-orphan")


class CodigoAcceso(Base):
    """Código de un solo uso para el ingreso (el CodigoQR del diagrama)."""
    __tablename__ = "codigo_acceso"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id", ondelete="CASCADE"), unique=True)
    codigo: Mapped[str] = mapped_column(String(12), unique=True)
    valido_desde: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valido_hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    generado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reserva: Mapped[Reserva] = relationship(back_populates="codigo")


class Pago(Base):
    __tablename__ = "pago"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id", ondelete="CASCADE"), unique=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    medio: Mapped[Optional[str]] = mapped_column(String(20))
    referencia: Mapped[Optional[str]] = mapped_column(String(40))
    pagado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    reembolsado_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    registrado_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reserva: Mapped[Reserva] = relationship(back_populates="pago")
    comprobante: Mapped[Optional["Comprobante"]] = relationship(
        back_populates="pago", uselist=False, cascade="all, delete-orphan")


class Comprobante(Base):
    __tablename__ = "comprobante"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pago_id: Mapped[int] = mapped_column(ForeignKey("pago.id", ondelete="CASCADE"), unique=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    medio: Mapped[str] = mapped_column(String(20))
    emitido_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pago: Mapped[Pago] = relationship(back_populates="comprobante")


class Conversacion(Base):
    __tablename__ = "conversacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    arrendatario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    arrendador_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cochera: Mapped[Cochera] = relationship()
    arrendatario: Mapped[Usuario] = relationship(foreign_keys=[arrendatario_id])
    arrendador: Mapped[Usuario] = relationship(foreign_keys=[arrendador_id])


class Mensaje(Base):
    __tablename__ = "mensaje"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversacion_id: Mapped[int] = mapped_column(ForeignKey("conversacion.id", ondelete="CASCADE"))
    emisor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    texto: Mapped[str] = mapped_column(Text)
    leido: Mapped[bool] = mapped_column(Boolean, default=False)
    enviado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notificacion(Base):
    __tablename__ = "notificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(30))
    titulo: Mapped[str] = mapped_column(String(120))
    texto: Mapped[str] = mapped_column(String(300))
    enlace: Mapped[Optional[str]] = mapped_column(String(200))
    leida: Mapped[bool] = mapped_column(Boolean, default=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Calificacion(Base):
    __tablename__ = "calificacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id", ondelete="CASCADE"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    destinatario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    estrellas: Mapped[int] = mapped_column(SmallInteger)
    comentario: Mapped[Optional[str]] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reserva: Mapped[Reserva] = relationship(back_populates="calificaciones")
    autor: Mapped[Usuario] = relationship(foreign_keys=[autor_id])
    destinatario: Mapped[Usuario] = relationship(foreign_keys=[destinatario_id])


class Reporte(Base):
    __tablename__ = "reporte"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cochera_id: Mapped[int] = mapped_column(ForeignKey("cochera.id", ondelete="CASCADE"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    motivo: Mapped[str] = mapped_column(String(30))
    detalle: Mapped[Optional[str]] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="pendiente")
    nota: Mapped[Optional[str]] = mapped_column(String(300))
    resuelto_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    resuelto_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cochera: Mapped[Cochera] = relationship()
    autor: Mapped[Usuario] = relationship(foreign_keys=[autor_id])


class Disputa(Base):
    """Incidencia o disputa sobre una reserva (Incidencia_Disputa del diagrama)."""
    __tablename__ = "disputa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reserva_id: Mapped[int] = mapped_column(ForeignKey("reserva.id", ondelete="CASCADE"))
    autor_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String(20))
    descripcion: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), default="abierta")
    resolucion: Mapped[Optional[str]] = mapped_column(Text)
    resuelto_por: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id"))
    resuelto_en: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    reserva: Mapped[Reserva] = relationship()
    autor: Mapped[Usuario] = relationship(foreign_keys=[autor_id])


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    usuario_id: Mapped[Optional[int]] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    accion: Mapped[str] = mapped_column(String(60))
    entidad: Mapped[str] = mapped_column(String(40))
    entidad_id: Mapped[Optional[int]] = mapped_column(Integer)
    detalle: Mapped[dict] = mapped_column(JSONB, default=dict)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped[Optional[Usuario]] = relationship()
