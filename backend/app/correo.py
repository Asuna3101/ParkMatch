"""Correo saliente (US-01 y US-03).

Si el archivo .env trae un servidor SMTP, el correo se envía de verdad.
Si no, se escribe en la consola del backend y en correos_enviados.log, que
es lo que se usa en la demostración del MVP.
"""
import smtplib
from datetime import datetime
from email.message import EmailMessage

from . import config

ARCHIVO = config.RAIZ / "correos_enviados.log"


def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    """Nunca lanza una excepción: un correo que falla no debe tumbar la operación."""
    if config.SMTP_HOST:
        try:
            mensaje = EmailMessage()
            mensaje["From"] = config.SMTP_REMITENTE
            mensaje["To"] = destinatario
            mensaje["Subject"] = asunto
            mensaje.set_content(cuerpo)
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PUERTO, timeout=10) as servidor:
                servidor.starttls()
                if config.SMTP_USUARIO:
                    servidor.login(config.SMTP_USUARIO, config.SMTP_CLAVE)
                servidor.send_message(mensaje)
            return
        except Exception as error:  # se registra y se sigue con el respaldo
            print(f"[correo] No se pudo enviar por SMTP: {error}")

    texto = (f"\n----- CORREO (simulado) {datetime.now(config.ZONA):%Y-%m-%d %H:%M} -----\n"
             f"Para:   {destinatario}\nAsunto: {asunto}\n\n{cuerpo}\n"
             f"------------------------------------------------\n")
    print(texto)
    try:
        with ARCHIVO.open("a", encoding="utf-8") as archivo:
            archivo.write(texto)
    except OSError:
        pass
