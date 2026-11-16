"""Dependencias compartidas: usuario autenticado y control por rol."""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario
from .security import leer_token

esquema = HTTPBearer(auto_error=False)


def usuario_actual(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(esquema),
    db: Session = Depends(get_db),
) -> Usuario:
    no_autorizado = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Inicia sesión para continuar.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciales is None:
        raise no_autorizado
    usuario_id = leer_token(credenciales.credentials)
    if usuario_id is None:
        raise no_autorizado
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise no_autorizado
    return usuario


def solo_rol(*roles: str):
    """Restringe un endpoint a uno o más roles."""
    def verificar(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tu tipo de cuenta no puede realizar esta acción.",
            )
        return usuario
    return verificar


solo_arrendador = solo_rol("arrendador")
solo_arrendatario = solo_rol("arrendatario")
solo_admin = solo_rol("administrador")


def usuario_opcional(
    credenciales: Optional[HTTPAuthorizationCredentials] = Depends(esquema),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    """Para pantallas públicas que muestran algo más si hay sesión."""
    if credenciales is None:
        return None
    usuario_id = leer_token(credenciales.credentials)
    return db.get(Usuario, usuario_id) if usuario_id is not None else None
