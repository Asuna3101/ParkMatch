"""Panel del administrador: moderación, disputas y verificación de identidad.

Requisitos 5, 31, 32 y 33 · US-04, US-23, US-24, US-25.
Todas las rutas exigen el rol «administrador».
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import auditoria, config, pasarela, schemas
from ..avisos import despachar, notificar
from ..database import get_db
from ..deps import solo_admin
from ..models import Cochera, Disputa, Reporte, Reserva, Usuario
from .comunidad import CARGA_DISPUTA, disputa_salida

router = APIRouter(prefix="/api/admin", tags=["Administración"])


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/resumen", response_model=schemas.ResumenAdmin)
def resumen(_: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    contar = lambda consulta: db.scalar(consulta) or 0  # noqa: E731
    return schemas.ResumenAdmin(
        usuarios=contar(select(func.count(Usuario.id))),
        cocheras_activas=contar(select(func.count(Cochera.id)).where(
            Cochera.activa.is_(True), Cochera.suspendida.is_(False))),
        cocheras_suspendidas=contar(select(func.count(Cochera.id)).where(Cochera.suspendida.is_(True))),
        reservas=contar(select(func.count(Reserva.id))),
        reportes_pendientes=contar(select(func.count(Reporte.id)).where(Reporte.estado == "pendiente")),
        disputas_abiertas=contar(select(func.count(Disputa.id)).where(Disputa.estado == "abierta")),
        verificaciones_pendientes=contar(select(func.count(Usuario.id)).where(
            Usuario.verificacion == "pendiente")),
    )


# ----------------------------------------------------------------- reportes
def _reporte_salida(db: Session, r: Reporte) -> schemas.ReporteSalida:
    c = r.cochera
    previos = db.scalar(select(func.count(Reporte.id)).where(
        Reporte.cochera_id == c.id, Reporte.id != r.id)) or 0
    return schemas.ReporteSalida(
        id=r.id, cochera_id=c.id, cochera_titulo=c.titulo, cochera_foto=c.fotos[0].url if c.fotos else None,
        cochera_suspendida=c.suspendida, arrendador_id=c.arrendador_id, arrendador_nombre=c.arrendador.nombre,
        autor_id=r.autor_id, autor_nombre=r.autor.nombre, motivo=r.motivo, detalle=r.detalle,
        estado=r.estado, nota=r.nota, creado_en=r.creado_en, resuelto_en=r.resuelto_en,
        reportes_previos=previos,
    )


_CARGA_REPORTE = (selectinload(Reporte.autor),
                  selectinload(Reporte.cochera).selectinload(Cochera.fotos),
                  selectinload(Reporte.cochera).selectinload(Cochera.arrendador))


@router.get("/reportes", response_model=List[schemas.ReporteSalida])
def reportes(estado: Optional[str] = "pendiente", _: Usuario = Depends(solo_admin),
             db: Session = Depends(get_db)):
    consulta = select(Reporte).options(*_CARGA_REPORTE).order_by(Reporte.creado_en.desc()).limit(200)
    if estado:
        consulta = consulta.where(Reporte.estado == estado)
    return [_reporte_salida(db, r) for r in db.scalars(consulta)]


@router.post("/reportes/{reporte_id}/resolver", response_model=schemas.ReporteSalida)
def resolver_reporte(reporte_id: int, datos: schemas.ResolverReporteEntrada,
                     admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Procedente: el anuncio queda suspendido y deja de aparecer en la búsqueda (US-24)."""
    reporte = db.scalar(select(Reporte).where(Reporte.id == reporte_id).options(*_CARGA_REPORTE))
    if reporte is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos ese reporte.")
    if reporte.estado != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Este reporte ya fue resuelto.")
    reporte.estado = datos.decision
    reporte.nota = (datos.nota or "").strip() or None
    reporte.resuelto_por = admin.id
    reporte.resuelto_en = _ahora()
    cochera = reporte.cochera
    if datos.decision == "procedente" and not cochera.suspendida:
        cochera.suspendida = True
        cochera.motivo_suspension = reporte.nota or "El anuncio no cumple las normas de ParkMatch."
        notificar(db, cochera.arrendador_id, "moderacion", "Anuncio suspendido",
                  f"Suspendimos «{cochera.titulo}»: {cochera.motivo_suspension}", enlace="/mis-cocheras")
    auditoria.registrar(db, admin.id, f"reporte_{datos.decision}", "reporte", reporte.id,
                        cochera_id=cochera.id, arrendador_id=cochera.arrendador_id)
    db.commit()
    despachar(db)
    return _reporte_salida(db, reporte)


@router.post("/cocheras/{cochera_id}/reactivar", status_code=status.HTTP_204_NO_CONTENT)
def levantar_suspension(cochera_id: int, admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    cochera = db.get(Cochera, cochera_id)
    if cochera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa cochera.")
    if not cochera.suspendida:
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta cochera no está suspendida.")
    cochera.suspendida = False
    cochera.motivo_suspension = None
    auditoria.registrar(db, admin.id, "suspension_levantada", "cochera", cochera.id,
                        arrendador_id=cochera.arrendador_id)
    notificar(db, cochera.arrendador_id, "moderacion", "Anuncio habilitado",
              f"«{cochera.titulo}» puede volver a recibir reservas.", enlace="/mis-cocheras")
    db.commit()
    despachar(db)


# ----------------------------------------------------------------- disputas
@router.get("/disputas", response_model=List[schemas.DisputaSalida])
def disputas(estado: Optional[str] = "abierta", _: Usuario = Depends(solo_admin),
             db: Session = Depends(get_db)):
    consulta = select(Disputa).options(*CARGA_DISPUTA).order_by(Disputa.creado_en.desc()).limit(200)
    if estado:
        consulta = consulta.where(Disputa.estado == estado)
    return [disputa_salida(d) for d in db.scalars(consulta)]


@router.post("/disputas/{disputa_id}/resolver", response_model=schemas.DisputaSalida)
def resolver_disputa(disputa_id: int, datos: schemas.ResolverDisputaEntrada,
                     admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """Cierra la disputa y, si corresponde, devuelve el pago o cancela la reserva."""
    disputa = db.scalar(select(Disputa).where(Disputa.id == disputa_id).options(*CARGA_DISPUTA))
    if disputa is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa disputa.")
    if disputa.estado != "abierta":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta disputa ya fue resuelta.")
    reserva: Reserva = db.scalar(select(Reserva).where(Reserva.id == disputa.reserva_id)
                                 .options(selectinload(Reserva.pago), selectinload(Reserva.codigo),
                                          selectinload(Reserva.cochera)))

    if datos.accion == "cancelacion":
        if reserva.estado != "confirmada":
            raise HTTPException(status.HTTP_409_CONFLICT, "Solo se cancela una reserva confirmada que no empezó.")
        reserva.estado = "cancelada"
        if reserva.codigo is not None:
            db.delete(reserva.codigo)
    if datos.accion in ("reembolso", "cancelacion") and reserva.pago is not None:
        pago = reserva.pago
        if pago.estado == "pagado":
            if pago.medio == "tarjeta":
                pasarela.reembolsar(pago.referencia, pago.monto)
                pago.estado = "reembolsado"
                pago.reembolsado_en = _ahora()
            else:
                pago.estado = "por_devolver"
        elif pago.estado == "pendiente":
            db.delete(pago)
    elif datos.accion == "reembolso":
        raise HTTPException(status.HTTP_409_CONFLICT, "Esta reserva no tiene un pago que devolver.")

    disputa.estado = "resuelta"
    disputa.resolucion = datos.resolucion.strip()
    disputa.resuelto_por = admin.id
    disputa.resuelto_en = _ahora()
    auditoria.registrar(db, admin.id, "disputa_resuelta", "disputa", disputa.id, decision=datos.accion,
                        reserva_id=reserva.id, arrendador_id=reserva.cochera.arrendador_id,
                        arrendatario_id=reserva.arrendatario_id)
    for parte in (reserva.arrendatario_id, reserva.cochera.arrendador_id):
        notificar(db, parte, "disputa", "Disputa resuelta",
                  f"Resolvimos la disputa sobre «{reserva.cochera.titulo}».", enlace="/reservas")
    db.commit()
    despachar(db)
    db.expire_all()
    return disputa_salida(db.scalar(select(Disputa).where(Disputa.id == disputa_id).options(*CARGA_DISPUTA)))


# ------------------------------------------------------ verificación de identidad
@router.get("/verificaciones", response_model=List[schemas.VerificacionSalida])
def verificaciones(_: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    usuarios = db.scalars(select(Usuario).where(Usuario.verificacion == "pendiente")
                          .order_by(Usuario.creado_en)).all()
    return [schemas.VerificacionSalida(usuario_id=u.id, nombre=u.nombre, correo=u.correo, rol=u.rol,
                                       verificacion=u.verificacion, creado_en=u.creado_en) for u in usuarios]


@router.get("/verificaciones/{usuario_id}/documento")
def ver_documento(usuario_id: int, _: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    """El documento está en una carpeta privada: solo el administrador lo descarga."""
    u = db.get(Usuario, usuario_id)
    if u is None or not u.documento_url:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Esta persona no envió un documento.")
    ruta = (config.CARPETA_PRIVADA / u.documento_url).resolve()
    if config.CARPETA_PRIVADA.resolve() not in ruta.parents or not ruta.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos el documento.")
    return FileResponse(ruta)


@router.post("/verificaciones/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def resolver_verificacion(usuario_id: int, datos: schemas.ResolverVerificacionEntrada,
                          admin: Usuario = Depends(solo_admin), db: Session = Depends(get_db)):
    u = db.get(Usuario, usuario_id)
    if u is None or u.verificacion != "pendiente":
        raise HTTPException(status.HTTP_409_CONFLICT, "No hay una verificación pendiente para esta persona.")
    u.verificacion = "verificado" if datos.aprobar else "rechazado"
    auditoria.registrar(db, admin.id, f"verificacion_{u.verificacion}", "usuario", u.id)
    notificar(db, u.id, "verificacion",
              "Identidad verificada" if datos.aprobar else "Verificación rechazada",
              "Tu cuenta ya muestra la insignia de verificado." if datos.aprobar
              else "No pudimos validar el documento. Envía una foto más clara.", enlace="/perfil")
    db.commit()
    despachar(db)
