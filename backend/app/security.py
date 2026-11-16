"""Contraseñas con bcrypt (requisito 38), tokens JWT (requisito 39),
enlaces de recuperación (requisito 3) y cifrado de tarjetas (requisito 56)."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from . import config


def hash_contrasena(contrasena: str) -> str:
    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_contrasena(contrasena: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(contrasena.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False


def crear_token(usuario_id: int, rol: str) -> str:
    ahora = datetime.now(timezone.utc)
    datos = {
        "sub": str(usuario_id),
        "rol": rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=config.TOKEN_MINUTOS),
    }
    return jwt.encode(datos, config.SECRET_KEY, algorithm=config.ALGORITMO_JWT)


def leer_token(token: str) -> Optional[int]:
    """Devuelve el id del usuario si el token es válido; si no, None."""
    try:
        datos = jwt.decode(token, config.SECRET_KEY, algorithms=[config.ALGORITMO_JWT])
        return int(datos["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# ------------------------------------------------- enlaces de un solo uso
def nuevo_token() -> Tuple[str, str]:
    """Devuelve (token, hash). Al usuario se le envía el token; se guarda solo el hash."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O ni 1/I, para dictarlo sin errores


def nuevo_codigo(largo: int = 8) -> str:
    """Código de acceso aleatorio, legible y difícil de adivinar."""
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(largo))


# ------------------------------------------------------ cifrado simétrico
def _fernet() -> Fernet:
    clave = hashlib.sha256(config.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar(texto: str) -> str:
    return _fernet().encrypt(texto.encode("utf-8")).decode("utf-8")


def descifrar(cifrado: str) -> Optional[str]:
    try:
        return _fernet().decrypt(cifrado.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
