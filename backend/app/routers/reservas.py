"""Motor de reservas, pagos, acceso y salida.

Requisitos 21, 22, 23, 24, 25, 26, 27, 28 y 53 · US-08, US-16, US-17, US-18, US-19.
Aquí vive la respuesta al riesgo R-01: que dos personas no puedan
reservar la misma cochera en el mismo horario.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import auditoria, config, pasarela, schemas, tarifas
from ..avisos import despachar, notificar
from ..database import get_db
from ..deps import solo_arrendador, solo_arrendatario, usuario_actual
from ..disponibilidad import evaluar, hay_reserva_confirmada
from ..models import (CodigoAcceso, Cochera, Comprobante, MetodoPago, Pago, Reserva, Usuario)
from ..security import nuevo_codigo
from ..ws import gestor

router = APIRouter(prefix="/api", tags=["Reservas y pagos"])

VIGENTES_CON_CODIGO = ("confirmada", "en_curso")

_CARGA = (
    selectinload(Reserva.cochera).selectinload(Cochera.ubicacion),
    selectinload(Reserva.cochera).selectinload(Cochera.fotos),
    selectinload(Reserva.cochera).selectinload(Cochera.arrendador),
    selectinload(Reserva.arrendatario),
    selectinload(Reserva.pago).selectinload(Pago.comprobante),
    selectinload(Reserva.codigo),
    selectinload(Reserva.metodo_pago),
    selectinload(Reserva.calificaciones),
    selectinload(Reserva.disputas),
)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _reserva_o_404(db: Session, reserva_id: int) -> Reserva:
    reserva = db.scalar(select(Reserva).where(Reserva.id == reserva_id).options(*_CARGA)
                        .execution_options(populate_existing=True))
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa reserva.")
    return reserva


def _es_parte(reserva: Reserva, usuario: Usuario) -> bool:
    return usuario.id in (reserva.arrendatario_id, reserva.cochera.arrendador_id)


def _salida(r: Reserva, usuario: Usuario) -> schemas.ReservaSalida:
    c = r.cochera
    ahora = _ahora()
    es_arrendatario = usuario.id == r.arrendatario_id
    es_arrendador = usuario.id == c.arrendador_id

    pago = None
    if r.pago:
        pago = schemas.PagoSalida(
            id=r.pago.id, monto=float(r.pago.monto), estado=r.pago.estado, medio=r.pago.medio,
            referencia=r.pago.referencia, pagado_en=r.pago.pagado_en, reembolsado_en=r.pago.reembolsado_en,
            comprobante_id=r.pago.comprobante.id if r.pago.comprobante else None,
            comprobante_numero=r.pago.comprobante.numero if r.pago.comprobante else None,
        )

    codigo = None
    if r.codigo and es_arrendatario:
        codigo = schemas.CodigoSalida(
            codigo=r.codigo.codigo, valido_desde=r.codigo.valido_desde, valido_hasta=r.codigo.valido_hasta,
            usado_en=r.codigo.usado_en, enlace=f"parkmatch://acceso/{r.codigo.codigo}",
        )

    otro_telefono = None
    if r.estado in VIGENTES_CON_CODIGO + ("finalizada",):
        otro = c.arrendador if es_arrendatario else r.arrendatario
        otro_telefono = otro.telefono if (es_arrendatario or es_arrendador) else None

    total_final = Decimal(r.costo_total) + Decimal(r.cargo_exceso or 0) + Decimal(r.penalizacion or 0)
    puede_cancelar = es_arrendatario and (
        r.estado == "solicitada"
        or (r.estado == "confirmada" and r.inicio > ahora)
    )
    devolucion = (r.estado == "confirmada" and r.inicio - ahora >= timedelta(hours=config.HORAS_CANCELACION))

    propia = next((x for x in r.calificaciones if x.autor_id == usuario.id), None)
    puede_calificar = (r.estado == "finalizada" and (es_arrendatario or es_arrendador)
                       and propia is None
                       and ahora - (r.salida_real or r.fin) <= timedelta(days=config.DIAS_PARA_CALIFICAR))

    return schemas.ReservaSalida(
        puede_calificar=puede_calificar, mi_calificacion=propia.estrellas if propia else None,
        disputa_abierta=any(d.estado == "abierta" for d in r.disputas),
        id=r.id, cochera_id=c.id, cochera_titulo=c.titulo,
        cochera_direccion=f"{c.ubicacion.direccion}, {c.ubicacion.distrito}",
        cochera_foto=c.fotos[0].url if c.fotos else None,
        arrendador_id=c.arrendador_id, arrendador_nombre=c.arrendador.nombre,
        arrendatario_id=r.arrendatario_id, arrendatario_nombre=r.arrendatario.nombre,
        arrendatario_verificado=r.arrendatario.verificacion == "verificado",
        otro_telefono=otro_telefono,
        inicio=r.inicio, fin=r.fin, estado=r.estado, costo_total=float(r.costo_total),
        motivo_rechazo=r.motivo_rechazo,
        medio_pago=r.medio_pago,
        tarjeta=(f"{r.metodo_pago.marca} •••• {r.metodo_pago.ultimos4}" if r.metodo_pago else None),
        ingreso_real=r.ingreso_real, salida_real=r.salida_real,
        minutos_exceso=r.minutos_exceso or 0, cargo_exceso=float(r.cargo_exceso or 0),
        penalizacion=float(r.penalizacion or 0), total_final=float(total_final),
        creado_en=r.creado_en, pago=pago, codigo=codigo,
        puede_cancelar=puede_cancelar, devolucion_si_cancela=devolucion,
    )


def _avisar(db: Session, usuario_id: int, tipo: str, titulo: str, texto: str) -> None:
    notificar(db, usuario_id, tipo, titulo, texto, enlace="/reservas")


def _evento(usuario_id: int, evento: str, cochera_titulo: str) -> None:
    """Aviso instantáneo por WebSocket. Se envía solo después de guardar la transacción."""
    gestor.enviar_desde_hilo([usuario_id], {"tipo": "reserva", "evento": evento, "cochera": cochera_titulo})


def _numero_comprobante(db: Session) -> str:
    total = db.scalar(select(func.count()).select_from(Comprobante)) or 0
    return f"PM-{total + 1:06d}"


def _cobrar_con_tarjeta(reserva: Reserva, monto: Decimal):
    """Cobro simulado con la tarjeta de la reserva. Devuelve el resultado de la pasarela."""
    return pasarela.cobrar(reserva.metodo_pago, monto)


# ------------------------------------------------------------- solicitar
@router.post("/reservas", response_model=schemas.ReservaSalida, status_code=status.HTTP_201_CREATED)
def solicitar(datos: schemas.ReservaEntrada, usuario: Usuario = Depends(solo_arrendatario),
              db: Session = Depends(get_db)):
    """El arrendatario pide un horario. Queda por confirmar hasta que el dueño lo acepte."""
    cochera = db.get(Cochera, datos.cochera_id)
    if cochera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa cochera.")
    if cochera.arrendador_id == usuario.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes reservar tu propia cochera.")

    motivo, costo, _ = evaluar(db, cochera, datos.inicio, datos.fin)
    if motivo:
        raise HTTPException(status.HTTP_409_CONFLICT, motivo)

    # No se permiten dos solicitudes pendientes del mismo usuario para horarios que se cruzan.
    duplicada = db.scalar(select(Reserva.id).where(
        Reserva.cochera_id == cochera.id, Reserva.arrendatario_id == usuario.id,
        Reserva.estado == "solicitada", Reserva.inicio < datos.fin, Reserva.fin > datos.inicio))
    if duplicada:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya enviaste una solicitud para ese horario.")

    metodo = None
    if datos.medio_pago == "tarjeta":
        metodo = db.scalar(select(MetodoPago).where(
            MetodoPago.id == datos.metodo_pago_id, MetodoPago.usuario_id == usuario.id))
        if metodo is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Esa tarjeta no está registrada en tu cuenta.")

    reserva = Reserva(
        cochera_id=cochera.id, arrendatario_id=usuario.id, inicio=datos.inicio, fin=datos.fin,
        estado="solicitada", costo_total=costo, medio_pago=datos.medio_pago,
        metodo_pago_id=metodo.id if metodo else None,
    )
    db.add(reserva)
    db.flush()
    auditoria.registrar(db, usuario.id, "reserva_solicitada", "reserva", reserva.id,
                        cochera_id=cochera.id, arrendador_id=cochera.arrendador_id,
                        arrendatario_id=usuario.id, medio_pago=datos.medio_pago, costo_total=float(costo))
    _avisar(db, cochera.arrendador_id, "solicitud", "Nueva solicitud de reserva",
            f"Alguien quiere reservar «{cochera.titulo}».")
    db.commit()
    _evento(cochera.arrendador_id, "solicitada", cochera.titulo)
    despachar(db)
    return _salida(_reserva_o_404(db, reserva.id), usuario)


@router.get("/reservas/mias", response_model=List[schemas.ReservaSalida])
def mis_reservas(usuario: Usuario = Depends(solo_arrendatario), db: Session = Depends(get_db)):
    reservas = db.scalars(select(Reserva).where(Reserva.arrendatario_id == usuario.id)
                          .options(*_CARGA).order_by(Reserva.inicio.desc())).all()
    return [_salida(r, usuario) for r in reservas]


@router.get("/reservas/recibidas", response_model=List[schemas.ReservaSalida])
def reservas_recibidas(usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    reservas = db.scalars(
        select(Reserva).join(Cochera, Cochera.id == Reserva.cochera_id)
        .where(Cochera.arrendador_id == usuario.id).options(*_CARGA)
        .order_by(Reserva.inicio.desc())
    ).all()
    return [_salida(r, usuario) for r in reservas]


# --------------------------------------------------------------- confirmar
@router.post("/reservas/{reserva_id}/confirmar", response_model=schemas.ReservaSalida)
def confirmar(reserva_id: int, usuario: Usuario = Depends(solo_arrendador),
              db: Session = Depends(get_db)):
    """El arrendador acepta la solicitud y el horario queda bloqueado (US-17).

    Dos barreras contra la doble reserva:
      1. Se bloquea la fila de la cochera (SELECT … FOR UPDATE).
      2. La restricción reserva_sin_solape de la base de datos rechaza el cruce.
    Si la reserva se pagó con tarjeta, el cobro se hace aquí: si el banco la
    rechaza, la reserva no se confirma.
    """
    previa = _reserva_o_404(db, reserva_id)
    if previa.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta solicitud no es de una de tus cocheras.")

    db.execute(select(Cochera.id).where(Cochera.id == previa.cochera_id).with_for_update())
    reserva = db.scalar(
        select(Reserva).where(Reserva.id == reserva_id)
        .with_for_update().execution_options(populate_existing=True)
    )

    if reserva.estado != "solicitada":
        estado = reserva.estado
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"La solicitud ya fue {estado}.")
    if reserva.inicio <= _ahora():
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "El horario de esta solicitud ya pasó.")
    if hay_reserva_confirmada(db, reserva.cochera_id, reserva.inicio, reserva.fin):
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya está reservado por otra persona.")

    pago = Pago(reserva_id=reserva.id, monto=reserva.costo_total, estado="pendiente")
    if reserva.medio_pago == "tarjeta":
        reserva_con_tarjeta = _reserva_o_404(db, reserva.id)
        resultado = _cobrar_con_tarjeta(reserva_con_tarjeta, reserva.costo_total)
        if not resultado.ok:
            db.rollback()
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                                f"El pago con tarjeta fue rechazado: {resultado.motivo}")
        pago.estado = "pagado"
        pago.medio = "tarjeta"
        pago.referencia = resultado.referencia
        pago.pagado_en = _ahora()

    reserva.estado = "confirmada"
    db.add(pago)
    db.flush()
    db.add(CodigoAcceso(
        reserva_id=reserva.id,
        codigo=nuevo_codigo(8),
        valido_desde=reserva.inicio - timedelta(minutes=config.MINUTOS_ANTES_INGRESO),
        valido_hasta=reserva.fin,
    ))

    # Las demás solicitudes que se cruzan con este horario ya no pueden atenderse.
    cruzadas = db.scalars(select(Reserva).where(
        Reserva.cochera_id == reserva.cochera_id, Reserva.id != reserva.id,
        Reserva.estado == "solicitada", Reserva.inicio < reserva.fin, Reserva.fin > reserva.inicio,
    )).all()
    for otra in cruzadas:
        otra.estado = "rechazada"
        otra.motivo_rechazo = "El horario fue reservado por otra persona."
        _avisar(db, otra.arrendatario_id, "reserva", "Solicitud rechazada",
                f"El horario que pediste en «{reserva.cochera.titulo}» ya fue reservado.")
        auditoria.registrar(db, None, "reserva_rechazada_por_cruce", "reserva", otra.id,
                            reserva_confirmada=reserva.id, arrendador_id=usuario.id,
                            arrendatario_id=otra.arrendatario_id)

    auditoria.registrar(db, usuario.id, "reserva_confirmada", "reserva", reserva.id,
                        cochera_id=reserva.cochera_id, arrendador_id=usuario.id,
                        arrendatario_id=reserva.arrendatario_id, costo_total=float(reserva.costo_total),
                        medio_pago=reserva.medio_pago)
    _avisar(db, reserva.arrendatario_id, "reserva", "Reserva confirmada",
            f"Tu reserva en «{reserva.cochera.titulo}» fue confirmada. Tu código de acceso ya está disponible.")
    try:
        db.commit()
    except IntegrityError:
        # Barrera 2: la base de datos detectó el cruce.
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya está reservado por otra persona.")

    _evento(reserva.arrendatario_id, "confirmada", reserva.cochera.titulo)
    despachar(db)
    for otra in cruzadas:
        _evento(otra.arrendatario_id, "rechazada", reserva.cochera.titulo)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


# ------------------------------------------------------ rechazar y cancelar
@router.post("/reservas/{reserva_id}/rechazar", response_model=schemas.ReservaSalida)
def rechazar(reserva_id: int, datos: schemas.RechazoEntrada,
             usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta solicitud no es de una de tus cocheras.")
    if reserva.estado != "solicitada":
        raise HTTPException(status.HTTP_409_CONFLICT, f"La solicitud ya fue {reserva.estado}.")
    reserva.estado = "rechazada"
    reserva.motivo_rechazo = (datos.motivo or "").strip() or None
    auditoria.registrar(db, usuario.id, "reserva_rechazada", "reserva", reserva.id,
                        arrendador_id=usuario.id, arrendatario_id=reserva.arrendatario_id)
    _avisar(db, reserva.arrendatario_id, "reserva", "Solicitud rechazada",
            f"El dueño no aceptó tu solicitud en «{reserva.cochera.titulo}».")
    db.commit()
    _evento(reserva.arrendatario_id, "rechazada", reserva.cochera.titulo)
    despachar(db)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


@router.post("/reservas/{reserva_id}/cancelar", response_model=schemas.ReservaSalida)
def cancelar(reserva_id: int, usuario: Usuario = Depends(solo_arrendatario),
             db: Session = Depends(get_db)):
    """Cancela una solicitud o una reserva confirmada (requisito 53).

    Si la reserva está confirmada y se cancela con al menos HORAS_CANCELACION de
    anticipación, se devuelve el pago: en tarjeta, de inmediato; en pago
    acordado, queda como «por devolver» para que el dueño lo entregue.
    """
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.arrendatario_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es tuya.")
    if reserva.estado not in ("solicitada", "confirmada"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"La reserva ya fue {reserva.estado}.")
    if reserva.estado == "confirmada" and reserva.inicio <= _ahora():
        raise HTTPException(status.HTTP_409_CONFLICT, "La reserva ya empezó y no se puede cancelar.")

    estado_previo = reserva.estado
    devuelve = estado_previo == "confirmada" and reserva.inicio - _ahora() >= timedelta(hours=config.HORAS_CANCELACION)
    reembolso = None

    # Con pago registrado y dentro del plazo, se devuelve. Fuera de plazo, el pago se conserva.
    if reserva.pago and reserva.pago.estado == "pagado" and devuelve:
        if reserva.pago.medio == "tarjeta":
            reembolso = pasarela.reembolsar(reserva.pago.referencia, reserva.pago.monto).referencia
            reserva.pago.estado = "reembolsado"
            reserva.pago.reembolsado_en = _ahora()
        else:
            reserva.pago.estado = "por_devolver"

    # Un pago que nunca se hizo se elimina; el código de acceso deja de valer.
    if reserva.pago and reserva.pago.estado == "pendiente":
        db.delete(reserva.pago)
    if reserva.codigo is not None:
        db.delete(reserva.codigo)
    reserva.estado = "cancelada"
    auditoria.registrar(db, usuario.id, "reserva_cancelada", "reserva", reserva.id,
                        estado_previo=estado_previo, con_devolucion=devuelve,
                        arrendador_id=reserva.cochera.arrendador_id, arrendatario_id=usuario.id,
                        referencia_reembolso=reembolso)
    _avisar(db, reserva.cochera.arrendador_id, "reserva", "Reserva cancelada",
            f"Se canceló una reserva en «{reserva.cochera.titulo}».")
    db.commit()
    _evento(reserva.cochera.arrendador_id, "cancelada", reserva.cochera.titulo)
    despachar(db)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


# --------------------------------------------------------------------- pagos
@router.post("/pagos/{reserva_id}/recibido", response_model=schemas.ReservaSalida)
def marcar_pago_recibido(reserva_id: int, datos: schemas.PagoRecibidoEntrada,
                         usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """El arrendador registra el pago acordado fuera de la app y se emite el comprobante."""
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es de una de tus cocheras.")
    if reserva.estado not in VIGENTES_CON_CODIGO + ("finalizada",) or reserva.pago is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se registra el pago de una reserva confirmada.")
    if reserva.pago.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este pago ya no está pendiente.")

    pago = reserva.pago
    pago.estado = "pagado"
    pago.medio = datos.medio
    pago.pagado_en = _ahora()
    pago.registrado_por = usuario.id
    db.flush()
    db.add(Comprobante(pago_id=pago.id, numero=_numero_comprobante(db), monto=pago.monto, medio=datos.medio))
    auditoria.registrar(db, usuario.id, "pago_recibido", "pago", pago.id,
                        reserva_id=reserva.id, monto=float(pago.monto), medio=datos.medio,
                        arrendador_id=usuario.id, arrendatario_id=reserva.arrendatario_id)
    _avisar(db, reserva.arrendatario_id, "pago", "Pago registrado",
            f"El dueño registró tu pago de S/ {float(pago.monto):.2f} en «{reserva.cochera.titulo}».")
    db.commit()
    _evento(reserva.arrendatario_id, "pago_recibido", reserva.cochera.titulo)
    despachar(db)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


@router.post("/pagos/{reserva_id}/devuelto", response_model=schemas.ReservaSalida)
def marcar_devuelto(reserva_id: int, usuario: Usuario = Depends(solo_arrendador),
                    db: Session = Depends(get_db)):
    """El arrendador confirma que devolvió en efectivo un pago que debía reintegrarse."""
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es de una de tus cocheras.")
    if reserva.pago is None or reserva.pago.estado != "por_devolver":
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay un pago pendiente de devolver.")
    reserva.pago.estado = "reembolsado"
    reserva.pago.reembolsado_en = _ahora()
    auditoria.registrar(db, usuario.id, "pago_devuelto", "pago", reserva.pago.id,
                        reserva_id=reserva.id, monto=float(reserva.pago.monto))
    db.commit()
    return _salida(_reserva_o_404(db, reserva_id), usuario)


# ------------------------------------------------------- acceso y salida
@router.get("/reservas/{reserva_id}/qr")
def codigo_qr(reserva_id: int, usuario: Usuario = Depends(solo_arrendatario), db: Session = Depends(get_db)):
    """Imagen PNG del código de acceso. Solo la ve el arrendatario y solo con reserva vigente (requisito 27)."""
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.arrendatario_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es tuya.")
    if reserva.codigo is None or reserva.estado not in VIGENTES_CON_CODIGO:
        raise HTTPException(status.HTTP_409_CONFLICT, "Aún no hay un código de acceso para esta reserva.")
    import io
    import qrcode
    imagen = qrcode.make(f"parkmatch://acceso/{reserva.codigo.codigo}")
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")



@router.post("/reservas/{reserva_id}/ingreso", response_model=schemas.ReservaSalida)
def registrar_ingreso(reserva_id: int, datos: schemas.ValidarCodigoEntrada,
                      usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """El arrendador escanea o escribe el código del arrendatario (requisito 27)."""
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es de una de tus cocheras.")
    if reserva.estado != "confirmada" or reserva.codigo is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta reserva no está lista para el ingreso.")
    ahora = _ahora()
    if reserva.codigo.usado_en is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Este código ya fue usado.")
    if ahora < reserva.codigo.valido_desde:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "El código todavía no es válido. Se activa 30 minutos antes del horario.")
    if reserva.codigo.codigo != datos.codigo:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El código no corresponde a esta reserva.")

    reserva.codigo.usado_en = ahora
    reserva.ingreso_real = ahora
    reserva.estado = "en_curso"
    auditoria.registrar(db, usuario.id, "ingreso_registrado", "reserva", reserva.id,
                        arrendador_id=usuario.id, arrendatario_id=reserva.arrendatario_id)
    _avisar(db, reserva.arrendatario_id, "reserva", "Ingreso registrado",
            f"Registramos tu ingreso a «{reserva.cochera.titulo}». Que tengas buen día.")
    db.commit()
    despachar(db)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


@router.post("/reservas/{reserva_id}/salida", response_model=schemas.ReservaSalida)
def registrar_salida(reserva_id: int, usuario: Usuario = Depends(solo_arrendador),
                     db: Session = Depends(get_db)):
    """Cierra la reserva. Si el auto se quedó más tiempo, calcula el cargo y la penalización (US-19)."""
    reserva = _reserva_o_404(db, reserva_id)
    if reserva.cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no es de una de tus cocheras.")
    if reserva.estado != "en_curso":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se cierra una reserva en curso.")

    ahora = _ahora()
    minutos, cargo, penalizacion = tarifas.calcular_exceso(reserva.fin, ahora, reserva.cochera.precio_hora)
    reserva.salida_real = ahora
    reserva.minutos_exceso = minutos
    reserva.cargo_exceso = cargo
    reserva.penalizacion = penalizacion
    reserva.estado = "finalizada"
    auditoria.registrar(db, usuario.id, "salida_registrada", "reserva", reserva.id,
                        minutos_exceso=minutos, cargo=float(cargo), penalizacion=float(penalizacion),
                        arrendador_id=usuario.id, arrendatario_id=reserva.arrendatario_id)
    if minutos:
        _avisar(db, reserva.arrendatario_id, "reserva", "Tiempo adicional",
                f"Saliste {minutos} min después del horario. Se suma S/ {float(cargo + penalizacion):.2f}.")
    db.commit()
    despachar(db)
    return _salida(_reserva_o_404(db, reserva_id), usuario)


# -------------------------------------------------------------- lectura
@router.get("/reservas/{reserva_id}", response_model=schemas.ReservaSalida)
def detalle_reserva(reserva_id: int, usuario: Usuario = Depends(usuario_actual),
                    db: Session = Depends(get_db)):
    reserva = _reserva_o_404(db, reserva_id)
    if not _es_parte(reserva, usuario):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no te corresponde.")
    return _salida(reserva, usuario)


@router.get("/pagos/arrendador", response_model=schemas.ResumenPagos)
def pagos_arrendador(usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """Estado de pagos de todas las reservas de sus cocheras (US-30)."""
    reservas = db.scalars(
        select(Reserva).join(Cochera, Cochera.id == Reserva.cochera_id)
        .where(Cochera.arrendador_id == usuario.id, Reserva.pago.has())
        .options(*_CARGA).order_by(Reserva.inicio.desc())
    ).all()
    filas, pagado, pendiente, reembolsado = [], 0.0, 0.0, 0.0
    for r in reservas:
        p = r.pago
        monto = float(p.monto)
        if p.estado == "pagado":
            pagado += monto
        elif p.estado == "pendiente":
            pendiente += monto
        elif p.estado in ("reembolsado", "por_devolver"):
            reembolsado += monto if p.estado == "reembolsado" else 0
        filas.append(schemas.PagoArrendador(
            reserva_id=r.id, cochera_id=r.cochera_id, cochera_titulo=r.cochera.titulo,
            arrendatario_nombre=r.arrendatario.nombre, inicio=r.inicio, fin=r.fin,
            estado_reserva=r.estado, monto=monto, estado=p.estado, medio=p.medio,
            pagado_en=p.pagado_en, reembolsado_en=p.reembolsado_en,
            comprobante_id=p.comprobante.id if p.comprobante else None,
            comprobante_numero=p.comprobante.numero if p.comprobante else None,
        ))
    return schemas.ResumenPagos(pagos=filas, total_pagado=round(pagado, 2),
                                total_pendiente=round(pendiente, 2), total_reembolsado=round(reembolsado, 2))


# ----------------------------------------------------------------- auditoría
@router.get("/auditoria", response_model=List[schemas.AuditoriaSalida])
def ver_auditoria(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Registro de actividad: el administrador ve todo; cada usuario, lo que le concierne (requisito 57)."""
    from ..models import LogAuditoria

    consulta = select(LogAuditoria).order_by(LogAuditoria.creado_en.desc()).limit(200)
    registros = db.scalars(consulta.options(selectinload(LogAuditoria.usuario))).all()
    salida = []
    for r in registros:
        d = r.detalle or {}
        propio = r.usuario_id == usuario.id or usuario.id in (d.get("arrendador_id"), d.get("arrendatario_id"))
        if usuario.rol != "administrador" and not propio:
            continue
        salida.append(schemas.AuditoriaSalida(
            id=r.id, accion=r.accion, entidad=r.entidad, entidad_id=r.entidad_id,
            usuario_nombre=r.usuario.nombre if r.usuario else None, detalle=d, creado_en=r.creado_en,
        ))
    return salida[:100]
