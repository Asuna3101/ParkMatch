"""ParkMatch — API del MVP.

Para levantarla:   uvicorn app.main:app --reload
Documentación interactiva:   http://localhost:8000/docs
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from . import config, schemas
from .database import SessionLocal
from .models import Conversacion, Usuario
from .routers import auth, chat, cocheras, cuenta, reservas
from .security import leer_token
from .ws import gestor

app = FastAPI(title="ParkMatch API", version="1.0.0",
              description="Marketplace P2P para la reserva de cocheras entre particulares.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ORIGENES_CORS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=config.CARPETA_UPLOADS), name="uploads")

app.include_router(auth.router)
app.include_router(cocheras.router)
app.include_router(reservas.router)
app.include_router(chat.router)
app.include_router(cuenta.router)

_ETIQUETAS = {
    "nombre": "El nombre", "correo": "El correo", "contrasena": "La contraseña",
    "telefono": "El teléfono", "rol": "El tipo de cuenta", "texto": "El mensaje",
    "medio": "El medio de pago", "inicio": "La hora de ingreso", "fin": "La hora de salida",
    "precio_hora": "El precio por hora", "franjas": "El calendario",
}
_MOTIVOS = {
    "missing": "es obligatorio.",
    "string_too_short": "es demasiado corto.",
    "string_too_long": "es demasiado largo.",
    "greater_than": "debe ser mayor que cero.",
    "literal_error": "no es una opción válida.",
    "too_short": "necesita al menos un elemento.",
}


@app.exception_handler(RequestValidationError)
async def error_de_validacion(request: Request, error: RequestValidationError):
    """Convierte el primer error de validación en un mensaje legible en español."""
    primero = error.errors()[0]
    campo = next((p for p in reversed(primero["loc"]) if isinstance(p, str) and p != "body"), "")
    etiqueta = _ETIQUETAS.get(campo, f"El campo «{campo}»" if campo else "El dato enviado")
    tipo, original = primero["type"], primero["msg"]

    if "email address" in original:
        mensaje = "Escribe un correo válido, por ejemplo nombre@correo.com."
    elif tipo == "value_error":
        mensaje = original.replace("Value error, ", "")   # ya viene en español
    else:
        mensaje = f"{etiqueta} {_MOTIVOS.get(tipo, 'no es válido.')}"
    return JSONResponse(status_code=422, content={"detail": mensaje})


@app.get("/api/salud", tags=["Sistema"])
def salud():
    return {"estado": "ok"}


# ---------------------------------------------------------------- WebSocket
def _usuario_del_token(token: str):
    usuario_id = leer_token(token)
    if usuario_id is None:
        return None
    with SessionLocal() as db:
        return db.get(Usuario, usuario_id)


def _procesar_mensaje(usuario_id: int, conversacion_id: int, texto: str):
    """Valida, guarda y devuelve (destinatarios, evento). Corre en un hilo."""
    with SessionLocal() as db:
        conversacion = db.get(Conversacion, conversacion_id)
        if conversacion is None or usuario_id not in (conversacion.arrendatario_id, conversacion.arrendador_id):
            return None
        evento = chat.guardar_mensaje(db, conversacion, usuario_id, texto)
        return [conversacion.arrendatario_id, conversacion.arrendador_id], evento


@app.websocket("/ws")
async def canal(ws: WebSocket, token: str = ""):
    """Canal en tiempo real. El cliente se identifica con su token JWT.

    Cliente → servidor:  {"tipo": "mensaje", "conversacion_id": 1, "texto": "Hola"}
    Servidor → cliente:  {"tipo": "mensaje", "mensaje": {...}}
                         {"tipo": "reserva", "evento": "confirmada", ...}
    """
    usuario = await run_in_threadpool(_usuario_del_token, token)
    if usuario is None:
        await ws.close(code=4401)
        return

    await gestor.conectar(usuario.id, ws)
    try:
        while True:
            datos = await ws.receive_json()
            if datos.get("tipo") != "mensaje":
                continue
            try:
                entrada = schemas.MensajeEntrada(texto=str(datos.get("texto", "")))
                conversacion_id = int(datos.get("conversacion_id"))
            except (ValidationError, TypeError, ValueError):
                await ws.send_json({"tipo": "error", "detalle": "El mensaje no es válido."})
                continue
            resultado = await run_in_threadpool(_procesar_mensaje, usuario.id, conversacion_id, entrada.texto)
            if resultado is None:
                await ws.send_json({"tipo": "error", "detalle": "No participas en esa conversación."})
                continue
            destinatarios, evento = resultado
            await gestor.enviar(destinatarios, evento)
    except WebSocketDisconnect:
        pass
    finally:
        gestor.desconectar(usuario.id, ws)
