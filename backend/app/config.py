"""Configuración de la aplicación, leída del archivo .env."""
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/parkmatch",
)
SECRET_KEY = os.getenv("SECRET_KEY", "clave-insegura-solo-para-desarrollo")
ALGORITMO_JWT = "HS256"
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "480"))

ORIGENES_CORS = [
    o.strip()
    for o in os.getenv("ORIGENES_CORS", "http://localhost:5173").split(",")
    if o.strip()
]

ZONA = ZoneInfo(os.getenv("ZONA_HORARIA", "America/Lima"))

# Dirección del frontend: se usa para armar los enlaces de los correos y del QR.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")

# Modo demostración: como no hay servidor de correo, el enlace para recuperar
# la contraseña también se devuelve en la respuesta, para poder probarlo.
MODO_DEMO = os.getenv("MODO_DEMO", "true").lower() in ("1", "true", "si", "sí")

# Correo saliente (opcional). Si no se configura, los correos se escriben
# en la consola del backend y en el archivo correos_enviados.log.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PUERTO = int(os.getenv("SMTP_PUERTO", "587"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
SMTP_CLAVE = os.getenv("SMTP_CLAVE", "")
SMTP_REMITENTE = os.getenv("SMTP_REMITENTE", "ParkMatch <no-responder@parkmatch.pe>")

CARPETA_UPLOADS = RAIZ / "uploads"        # fotos públicas: cocheras y perfiles
CARPETA_UPLOADS.mkdir(exist_ok=True)
CARPETA_PRIVADA = RAIZ / "privado"        # documentos de identidad: nunca públicos
CARPETA_PRIVADA.mkdir(exist_ok=True)

# ---------------------------------------------------------- reglas de negocio
# Recuperación de contraseña (requisito 3): el enlace vale 24 horas.
HORAS_RECUPERACION = 24

# Penalización por exceso de tiempo (requisito 26 · US-19): además del tiempo
# adicional usado, se cobra un 10 % del precio por hora, prorrateado por minuto.
PENALIZACION_PORCENTAJE = 10

# Política de cancelación (requisito 53 · US-29): hay devolución si se cancela
# con al menos estas horas de anticipación al ingreso.
HORAS_CANCELACION = 2

# Código de acceso (requisito 25): sirve desde estos minutos antes del ingreso
# y hasta la hora de salida reservada.
MINUTOS_ANTES_INGRESO = 30

# Reglas del anuncio (requisito 6)
MIN_FOTOS = 3
MAX_FOTOS = 8
MAX_BYTES_FOTO = 5 * 1024 * 1024
TIPOS_FOTO = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
