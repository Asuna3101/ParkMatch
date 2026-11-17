"""Perfil, vehículos, verificación de identidad y recuperación de contraseña.

Requisitos 3, 4 y 5 · US-03, US-04, US-21.
"""
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from .. import archivos, auditoria, config, correo, reputacion, schemas
from ..database import get_db
from ..deps import usuario_actual
from ..models import Cochera, RecuperacionContrasena, Reserva, Usuario, Vehiculo
from ..security import hash_contrasena, hash_token, nuevo_token, verificar_contrasena

router = APIRouter(prefix="/api", tags=["Perfil"])

_MENSAJE_RECUPERAR = ("Si existe una cuenta con ese correo, te enviamos un enlace para "
                      "crear una nueva contraseña. Revisa tu bandeja de entrada.")


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _perfil(u: Usuario) -> schemas.PerfilSalida:
    return schemas.PerfilSalida(
        id=u.id, nombre=u.nombre, correo=u.correo, telefono=u.telefono, rol=u.rol,
        foto_url=u.foto_url, verificacion=u.verificacion, tiene_documento=bool(u.documento_url),
        creado_en=u.creado_en, vehiculos=[schemas.VehiculoSalida.model_validate(v) for v in u.vehiculos],
    )


# ---------------------------------------------------------- recuperación
@router.post("/auth/recuperar", response_model=schemas.RecuperarSalida)
def recuperar(datos: schemas.RecuperarEntrada, db: Session = Depends(get_db)):
    """Envía un enlace de un solo uso para restablecer la contraseña (US-03).

    La respuesta es la misma exista o no la cuenta, para no revelar qué correos
    están registrados. En modo demostración se devuelve también el enlace.
    """
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.correo) == datos.correo.lower()))
    if usuario is None:
        return schemas.RecuperarSalida(mensaje=_MENSAJE_RECUPERAR)

    # Un enlace nuevo invalida los anteriores que no se usaron.
    for previo in db.scalars(select(RecuperacionContrasena).where(
            RecuperacionContrasena.usuario_id == usuario.id, RecuperacionContrasena.usado_en.is_(None))):
        previo.usado_en = _ahora()

    token, token_hash = nuevo_token()
    db.add(RecuperacionContrasena(usuario_id=usuario.id, token_hash=token_hash,
                                  expira_en=_ahora() + timedelta(hours=config.HORAS_RECUPERACION)))
    auditoria.registrar(db, usuario.id, "recuperacion_solicitada", "usuario", usuario.id)
    db.commit()

    enlace = f"{config.FRONTEND_URL}/restablecer?token={token}"
    correo.enviar(usuario.correo, "Recupera tu contraseña de ParkMatch",
                  f"Hola, {usuario.nombre}.\n\nPara crear una nueva contraseña entra a este enlace "
                  f"(vale {config.HORAS_RECUPERACION} horas y sirve una sola vez):\n\n{enlace}\n\n"
                  "Si no lo pediste, ignora este correo.")
    return schemas.RecuperarSalida(mensaje=_MENSAJE_RECUPERAR,
                                   enlace_demo=enlace if config.MODO_DEMO else None)


@router.post("/auth/restablecer", status_code=status.HTTP_204_NO_CONTENT)
def restablecer(datos: schemas.RestablecerEntrada, db: Session = Depends(get_db)):
    registro = db.scalar(select(RecuperacionContrasena).where(
        RecuperacionContrasena.token_hash == hash_token(datos.token)).with_for_update())
    if registro is None or registro.usado_en is not None or registro.expira_en <= _ahora():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "El enlace no es válido o ya venció. Pide uno nuevo.")
    usuario = db.get(Usuario, registro.usuario_id)
    usuario.contrasena_hash = hash_contrasena(datos.contrasena)
    registro.usado_en = _ahora()
    auditoria.registrar(db, usuario.id, "contrasena_restablecida", "usuario", usuario.id)
    db.commit()


# ------------------------------------------------------------------ perfil
@router.get("/perfil", response_model=schemas.PerfilSalida)
def ver_perfil(usuario: Usuario = Depends(usuario_actual)):
    return _perfil(usuario)


@router.put("/perfil", response_model=schemas.PerfilSalida)
def editar_perfil(datos: schemas.PerfilEntrada, usuario: Usuario = Depends(usuario_actual),
                  db: Session = Depends(get_db)):
    usuario.nombre = datos.nombre
    usuario.telefono = (datos.telefono or "").strip() or None
    auditoria.registrar(db, usuario.id, "perfil_editado", "usuario", usuario.id)
    db.commit()
    return _perfil(usuario)


@router.post("/perfil/contrasena", status_code=status.HTTP_204_NO_CONTENT)
def cambiar_contrasena(datos: schemas.CambiarContrasenaEntrada, usuario: Usuario = Depends(usuario_actual),
                       db: Session = Depends(get_db)):
    if not verificar_contrasena(datos.actual, usuario.contrasena_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "La contraseña actual no es correcta.")
    usuario.contrasena_hash = hash_contrasena(datos.nueva)
    auditoria.registrar(db, usuario.id, "contrasena_cambiada", "usuario", usuario.id)
    db.commit()


@router.post("/perfil/foto", response_model=schemas.PerfilSalida)
def subir_foto(foto: UploadFile = File(...), usuario: Usuario = Depends(usuario_actual),
               db: Session = Depends(get_db)):
    usuario.foto_url = archivos.guardar_publica(foto, prefijo="perfil_")
    db.commit()
    return _perfil(usuario)


@router.post("/perfil/documento", response_model=schemas.PerfilSalida)
def subir_documento(documento: UploadFile = File(...), usuario: Usuario = Depends(usuario_actual),
                    db: Session = Depends(get_db)):
    """Foto del DNI para verificar la identidad (requisito 5). Se guarda fuera de /uploads."""
    if usuario.verificacion == "verificado":
        raise HTTPException(status.HTTP_409_CONFLICT, "Tu identidad ya está verificada.")
    usuario.documento_url = archivos.guardar_imagen(documento, config.CARPETA_PRIVADA, prefijo="dni_")
    usuario.verificacion = "pendiente"
    auditoria.registrar(db, usuario.id, "documento_enviado", "usuario", usuario.id)
    db.commit()
    return _perfil(usuario)


# --------------------------------------------------------------- vehículos
@router.post("/perfil/vehiculos", response_model=schemas.PerfilSalida, status_code=status.HTTP_201_CREATED)
def agregar_vehiculo(datos: schemas.VehiculoEntrada, usuario: Usuario = Depends(usuario_actual),
                     db: Session = Depends(get_db)):
    usuario.vehiculos.append(Vehiculo(**datos.model_dump()))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya registraste un vehículo con esa placa.")
    db.refresh(usuario)
    return _perfil(usuario)


@router.delete("/perfil/vehiculos/{vehiculo_id}", response_model=schemas.PerfilSalida)
def eliminar_vehiculo(vehiculo_id: int, usuario: Usuario = Depends(usuario_actual),
                      db: Session = Depends(get_db)):
    vehiculo = db.get(Vehiculo, vehiculo_id)
    if vehiculo is None or vehiculo.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos ese vehículo.")
    db.delete(vehiculo)
    db.commit()
    db.refresh(usuario)
    return _perfil(usuario)


# ---------------------------------------------------------- perfil público
@router.get("/usuarios/{usuario_id}", response_model=schemas.PerfilPublico)
def perfil_publico(usuario_id: int, db: Session = Depends(get_db)):
    """Reputación de una persona: estrellas, reseñas y cocheras activas (US-21)."""
    from .cocheras import _resumen

    u = db.get(Usuario, usuario_id)
    if u is None or u.rol == "administrador":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos a esa persona.")
    promedio, total = reputacion.promedio_usuario(db, u.id)

    finalizadas = select(func.count(Reserva.id)).where(Reserva.estado == "finalizada")
    if u.rol == "arrendador":
        finalizadas = finalizadas.join(Cochera, Cochera.id == Reserva.cochera_id).where(
            Cochera.arrendador_id == u.id)
    else:
        finalizadas = finalizadas.where(Reserva.arrendatario_id == u.id)

    cocheras: List[schemas.CocheraResumen] = []
    if u.rol == "arrendador":
        filas = db.scalars(select(Cochera).where(
            Cochera.arrendador_id == u.id, Cochera.activa.is_(True), Cochera.suspendida.is_(False))
            .options(selectinload(Cochera.ubicacion), selectinload(Cochera.fotos))).all()
        notas = reputacion.promedios_cocheras(db, [c.id for c in filas])
        cocheras = [_resumen(c, calificacion=notas.get(c.id)) for c in filas]

    return schemas.PerfilPublico(
        id=u.id, nombre=u.nombre, rol=u.rol, foto_url=u.foto_url,
        verificado=u.verificacion == "verificado", miembro_desde=u.creado_en,
        calificacion_promedio=promedio, total_calificaciones=total,
        transacciones_completadas=db.scalar(finalizadas) or 0,
        resenas=reputacion.resenas_usuario(db, u.id), cocheras=cocheras,
    )
