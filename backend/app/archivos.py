"""Guardado de imágenes subidas por los usuarios."""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from . import config


def guardar_imagen(archivo: UploadFile, carpeta: Path, prefijo: str = "") -> str:
    """Valida tipo y tamaño, guarda con un nombre aleatorio y devuelve ese nombre."""
    extension = config.TIPOS_FOTO.get(archivo.content_type or "")
    if extension is None:
        raise HTTPException(422, f"«{archivo.filename}» no es una imagen válida. Usa JPG, PNG o WebP.")
    contenido = archivo.file.read()
    if not contenido:
        raise HTTPException(422, f"«{archivo.filename}» está vacío.")
    if len(contenido) > config.MAX_BYTES_FOTO:
        raise HTTPException(422, f"«{archivo.filename}» pesa más de 5 MB.")
    nombre = f"{prefijo}{uuid.uuid4().hex}{extension}"
    (carpeta / nombre).write_bytes(contenido)
    return nombre


def guardar_publica(archivo: UploadFile, prefijo: str = "") -> str:
    """Para fotos que cualquiera puede ver. Devuelve la URL relativa."""
    return f"/uploads/{guardar_imagen(archivo, config.CARPETA_UPLOADS, prefijo)}"
