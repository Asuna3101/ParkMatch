"""Registro e inicio de sesión (requisitos 1 y 2 · US-01, US-02)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auditoria, schemas
from ..database import get_db
from ..deps import usuario_actual
from ..models import Usuario
from ..security import crear_token, hash_contrasena, verificar_contrasena

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/registro", response_model=schemas.SesionSalida, status_code=status.HTTP_201_CREATED)
def registro(datos: schemas.RegistroEntrada, db: Session = Depends(get_db)):
    correo = datos.correo.lower()
    usuario = Usuario(
        nombre=datos.nombre,
        correo=correo,
        contrasena_hash=hash_contrasena(datos.contrasena),
        telefono=datos.telefono,
        rol=datos.rol,
        acepto_datos_en=datetime.now(timezone.utc),
    )
    db.add(usuario)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo.")
    auditoria.registrar(db, usuario.id, "usuario_registrado", "usuario", usuario.id, rol=usuario.rol)
    db.commit()
    return schemas.SesionSalida(token=crear_token(usuario.id, usuario.rol), usuario=usuario)


@router.post("/login", response_model=schemas.SesionSalida)
def login(datos: schemas.LoginEntrada, db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.correo) == datos.correo.lower()))
    # Mismo mensaje en ambos casos: no se revela si el correo existe.
    if usuario is None or not verificar_contrasena(datos.contrasena, usuario.contrasena_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos.")
    return schemas.SesionSalida(token=crear_token(usuario.id, usuario.rol), usuario=usuario)


@router.get("/yo", response_model=schemas.UsuarioSalida)
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario
