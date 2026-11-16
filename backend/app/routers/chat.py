"""Chat entre arrendador y arrendatario (requisito 17 · US-13)."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import get_db
from ..deps import solo_arrendatario, usuario_actual
from ..models import Cochera, Conversacion, Mensaje, Usuario
from ..ws import gestor

router = APIRouter(prefix="/api/conversaciones", tags=["Chat"])


def _conversacion_o_403(db: Session, conversacion_id: int, usuario: Usuario) -> Conversacion:
    conversacion = db.get(Conversacion, conversacion_id)
    if conversacion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa conversación.")
    if usuario.id not in (conversacion.arrendatario_id, conversacion.arrendador_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No participas en esta conversación.")
    return conversacion


def guardar_mensaje(db: Session, conversacion: Conversacion, emisor_id: int, texto: str) -> dict:
    """Guarda el mensaje y devuelve el evento que se envía por WebSocket."""
    mensaje = Mensaje(conversacion_id=conversacion.id, emisor_id=emisor_id, texto=texto)
    db.add(mensaje)
    db.commit()
    return {
        "tipo": "mensaje",
        "mensaje": schemas.MensajeSalida.model_validate(mensaje).model_dump(mode="json"),
    }


@router.post("", response_model=schemas.ConversacionSalida)
def abrir(datos: schemas.ConversacionEntrada, usuario: Usuario = Depends(solo_arrendatario),
          db: Session = Depends(get_db)):
    """Abre la conversación con el dueño de una cochera, o devuelve la que ya existe."""
    cochera = db.get(Cochera, datos.cochera_id)
    if cochera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa cochera.")
    conversacion = db.scalar(select(Conversacion).where(
        Conversacion.cochera_id == cochera.id, Conversacion.arrendatario_id == usuario.id))
    if conversacion is None:
        conversacion = Conversacion(cochera_id=cochera.id, arrendatario_id=usuario.id,
                                    arrendador_id=cochera.arrendador_id)
        db.add(conversacion)
        db.commit()
    return schemas.ConversacionSalida(
        id=conversacion.id, cochera_id=cochera.id, cochera_titulo=cochera.titulo,
        otro_id=cochera.arrendador_id, otro_nombre=cochera.arrendador.nombre)


@router.get("", response_model=List[schemas.ConversacionSalida])
def listar(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    conversaciones = db.scalars(
        select(Conversacion)
        .where(or_(Conversacion.arrendatario_id == usuario.id, Conversacion.arrendador_id == usuario.id))
        .options(selectinload(Conversacion.cochera), selectinload(Conversacion.arrendatario),
                 selectinload(Conversacion.arrendador))
    ).all()

    salida = []
    for c in conversaciones:
        otro = c.arrendador if usuario.id == c.arrendatario_id else c.arrendatario
        ultimo = db.scalar(select(Mensaje).where(Mensaje.conversacion_id == c.id)
                           .order_by(Mensaje.enviado_en.desc(), Mensaje.id.desc()).limit(1))
        sin_leer = db.scalar(select(func.count()).select_from(Mensaje).where(
            Mensaje.conversacion_id == c.id, Mensaje.emisor_id != usuario.id, Mensaje.leido.is_(False)))
        salida.append(schemas.ConversacionSalida(
            id=c.id, cochera_id=c.cochera_id, cochera_titulo=c.cochera.titulo,
            otro_id=otro.id, otro_nombre=otro.nombre,
            ultimo_mensaje=ultimo.texto if ultimo else None,
            ultimo_en=ultimo.enviado_en if ultimo else c.creado_en,
            sin_leer=sin_leer or 0,
        ))
    salida.sort(key=lambda x: x.ultimo_en, reverse=True)
    return salida


@router.get("/{conversacion_id}/mensajes", response_model=List[schemas.MensajeSalida])
def mensajes(conversacion_id: int, usuario: Usuario = Depends(usuario_actual),
             db: Session = Depends(get_db)):
    """Historial de la conversación. Al abrirla, lo recibido queda como leído."""
    _conversacion_o_403(db, conversacion_id, usuario)
    db.execute(update(Mensaje).where(
        Mensaje.conversacion_id == conversacion_id, Mensaje.emisor_id != usuario.id,
        Mensaje.leido.is_(False)).values(leido=True))
    db.commit()
    return db.scalars(select(Mensaje).where(Mensaje.conversacion_id == conversacion_id)
                      .order_by(Mensaje.enviado_en, Mensaje.id)).all()


@router.post("/{conversacion_id}/mensajes", response_model=schemas.MensajeSalida,
             status_code=status.HTTP_201_CREATED)
def enviar(conversacion_id: int, datos: schemas.MensajeEntrada,
           usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    """Envía un mensaje por HTTP. Es el respaldo si el WebSocket no está conectado."""
    conversacion = _conversacion_o_403(db, conversacion_id, usuario)
    evento = guardar_mensaje(db, conversacion, usuario.id, datos.texto)
    gestor.enviar_desde_hilo([conversacion.arrendatario_id, conversacion.arrendador_id], evento)
    return evento["mensaje"]
