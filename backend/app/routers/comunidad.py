"""Calificaciones, notificaciones, reportes y disputas (lado del usuario).

Requisitos 18, 28, 29, 31 y 32 · US-15, US-20, US-22, US-23, US-25.
"""
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import auditoria, config, schemas
from ..avisos import despachar, notificar
from ..database import get_db
from ..deps import usuario_actual
from ..models import Calificacion, Cochera, Disputa, Notificacion, Reporte, Reserva, Usuario

router = APIRouter(prefix="/api", tags=["Comunidad"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _reserva_de_parte(db: Session, reserva_id: int, usuario: Usuario) -> Reserva:
    reserva = db.scalar(select(Reserva).where(Reserva.id == reserva_id)
                        .options(selectinload(Reserva.cochera), selectinload(Reserva.calificaciones)))
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa reserva.")
    if usuario.id not in (reserva.arrendatario_id, reserva.cochera.arrendador_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esta reserva no te corresponde.")
    return reserva


# ------------------------------------------------------------ calificaciones
@router.post("/reservas/{reserva_id}/calificar", status_code=status.HTTP_201_CREATED)
def calificar(reserva_id: int, datos: schemas.CalificacionEntrada,
              usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Cada parte califica a la otra una sola vez, al terminar la reserva (US-20)."""
    reserva = _reserva_de_parte(db, reserva_id, usuario)
    if reserva.estado != "finalizada":
        raise HTTPException(status.HTTP_409_CONFLICT, "Solo se califica una reserva finalizada.")
    if _ahora() - (reserva.salida_real or reserva.fin) > timedelta(days=config.DIAS_PARA_CALIFICAR):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"El plazo para calificar ({config.DIAS_PARA_CALIFICAR} días) ya venció.")
    es_arrendatario = usuario.id == reserva.arrendatario_id
    destinatario = reserva.cochera.arrendador_id if es_arrendatario else reserva.arrendatario_id

    calificacion = Calificacion(reserva_id=reserva.id, autor_id=usuario.id, destinatario_id=destinatario,
                                estrellas=datos.estrellas,
                                comentario=(datos.comentario or "").strip() or None)
    db.add(calificacion)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya calificaste esta reserva.")
    auditoria.registrar(db, usuario.id, "calificacion_registrada", "reserva", reserva.id,
                        estrellas=datos.estrellas, destinatario_id=destinatario)
    notificar(db, destinatario, "calificacion", "Recibiste una calificación",
              f"{usuario.nombre} te calificó con {datos.estrellas} estrella(s).", enlace=f"/usuarios/{destinatario}")
    db.commit()
    despachar(db)
    return {"id": calificacion.id, "estrellas": calificacion.estrellas}


# ------------------------------------------------------------ notificaciones
@router.get("/notificaciones", response_model=schemas.BandejaNotificaciones)
def bandeja(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Últimas notificaciones dentro de la aplicación (US-15)."""
    avisos = db.scalars(select(Notificacion).where(Notificacion.usuario_id == usuario.id)
                        .order_by(Notificacion.creado_en.desc(), Notificacion.id.desc()).limit(50)).all()
    sin_leer = db.scalar(select(func.count(Notificacion.id)).where(
        Notificacion.usuario_id == usuario.id, Notificacion.leida.is_(False))) or 0
    return schemas.BandejaNotificaciones(
        sin_leer=sin_leer, notificaciones=[schemas.NotificacionSalida.model_validate(a) for a in avisos])


@router.post("/notificaciones/leidas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_leidas(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    db.execute(update(Notificacion).where(Notificacion.usuario_id == usuario.id,
                                          Notificacion.leida.is_(False)).values(leida=True))
    db.commit()


# ----------------------------------------------------------------- reportes
@router.post("/cocheras/{cochera_id}/reportes", status_code=status.HTTP_201_CREATED)
def reportar(cochera_id: int, datos: schemas.ReporteEntrada,
             usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Cualquier persona con sesión puede reportar un anuncio (US-23)."""
    cochera = db.get(Cochera, cochera_id)
    if cochera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa cochera.")
    if cochera.arrendador_id == usuario.id:
        raise HTTPException(status.HTTP_409_CONFLICT, "No puedes reportar tu propia cochera.")
    reporte = Reporte(cochera_id=cochera.id, autor_id=usuario.id, motivo=datos.motivo,
                      detalle=(datos.detalle or "").strip() or None)
    db.add(reporte)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Ya reportaste esta cochera. El equipo lo está revisando.")
    auditoria.registrar(db, usuario.id, "cochera_reportada", "cochera", cochera.id, motivo=datos.motivo)
    for admin_id in db.scalars(select(Usuario.id).where(Usuario.rol == "administrador")):
        notificar(db, admin_id, "moderacion", "Nuevo reporte",
                  f"Reportaron la cochera «{cochera.titulo}».", enlace="/admin")
    db.commit()
    despachar(db)
    return {"id": reporte.id, "mensaje": "Gracias. El equipo de ParkMatch revisará el anuncio."}


# ----------------------------------------------------------------- disputas
def disputa_salida(d: Disputa) -> schemas.DisputaSalida:
    r = d.reserva
    return schemas.DisputaSalida(
        id=d.id, reserva_id=r.id, cochera_titulo=r.cochera.titulo,
        autor_id=d.autor_id, autor_nombre=d.autor.nombre,
        arrendador_id=r.cochera.arrendador_id, arrendador_nombre=r.cochera.arrendador.nombre,
        arrendatario_id=r.arrendatario_id, arrendatario_nombre=r.arrendatario.nombre,
        tipo=d.tipo, descripcion=d.descripcion, estado=d.estado, resolucion=d.resolucion,
        creado_en=d.creado_en, resuelto_en=d.resuelto_en,
        inicio=r.inicio, fin=r.fin, estado_reserva=r.estado,
        monto=float(r.pago.monto) if r.pago else None, estado_pago=r.pago.estado if r.pago else None,
    )


CARGA_DISPUTA = (
    selectinload(Disputa.autor),
    selectinload(Disputa.reserva).selectinload(Reserva.cochera).selectinload(Cochera.arrendador),
    selectinload(Disputa.reserva).selectinload(Reserva.arrendatario),
    selectinload(Disputa.reserva).selectinload(Reserva.pago),
)


@router.post("/reservas/{reserva_id}/disputas", response_model=schemas.DisputaSalida,
             status_code=status.HTTP_201_CREATED)
def abrir_disputa(reserva_id: int, datos: schemas.DisputaEntrada,
                  usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Una de las partes abre una incidencia sobre la reserva (US-25)."""
    reserva = _reserva_de_parte(db, reserva_id, usuario)
    if reserva.estado in ("solicitada", "rechazada"):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Solo se abre una disputa sobre una reserva que llegó a confirmarse.")
    abierta = db.scalar(select(Disputa.id).where(Disputa.reserva_id == reserva.id,
                                                 Disputa.estado == "abierta"))
    if abierta:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya hay una disputa abierta sobre esta reserva.")
    disputa = Disputa(reserva_id=reserva.id, autor_id=usuario.id, tipo=datos.tipo,
                      descripcion=datos.descripcion.strip())
    db.add(disputa)
    db.flush()
    otro = reserva.cochera.arrendador_id if usuario.id == reserva.arrendatario_id else reserva.arrendatario_id
    auditoria.registrar(db, usuario.id, "disputa_abierta", "disputa", disputa.id, reserva_id=reserva.id,
                        tipo=datos.tipo, arrendador_id=reserva.cochera.arrendador_id,
                        arrendatario_id=reserva.arrendatario_id)
    notificar(db, otro, "disputa", "Se abrió una disputa",
              f"Se abrió una disputa sobre la reserva en «{reserva.cochera.titulo}».", enlace="/reservas")
    for admin_id in db.scalars(select(Usuario.id).where(Usuario.rol == "administrador")):
        notificar(db, admin_id, "moderacion", "Nueva disputa",
                  f"Disputa sobre «{reserva.cochera.titulo}».", enlace="/admin")
    db.commit()
    despachar(db)
    return disputa_salida(db.scalar(select(Disputa).where(Disputa.id == disputa.id).options(*CARGA_DISPUTA)))


@router.get("/disputas/mias", response_model=List[schemas.DisputaSalida])
def mis_disputas(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    disputas = db.scalars(
        select(Disputa).join(Reserva, Reserva.id == Disputa.reserva_id)
        .join(Cochera, Cochera.id == Reserva.cochera_id)
        .where((Reserva.arrendatario_id == usuario.id) | (Cochera.arrendador_id == usuario.id))
        .options(*CARGA_DISPUTA).order_by(Disputa.creado_en.desc())
    ).all()
    return [disputa_salida(d) for d in disputas]
