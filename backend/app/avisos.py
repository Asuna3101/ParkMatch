"""Notificaciones dentro de la aplicación (requisitos 18, 19, 20 y 55).

Cada aviso se guarda en la tabla notificacion y, una vez confirmada la
transacción, se entrega en tiempo real por el WebSocket a quien esté conectado.
"""
from typing import List, Optional

from sqlalchemy.orm import Session

from .models import Notificacion
from .ws import gestor

_CLAVE = "avisos_pendientes"


def notificar(db: Session, usuario_id: int, tipo: str, titulo: str, texto: str,
              enlace: Optional[str] = None) -> Notificacion:
    """Agrega la notificación a la transacción en curso. Se entrega con despachar()."""
    aviso = Notificacion(usuario_id=usuario_id, tipo=tipo, titulo=titulo[:120],
                         texto=texto[:300], enlace=enlace)
    db.add(aviso)
    db.info.setdefault(_CLAVE, []).append(aviso)
    return aviso


def _evento(aviso: Notificacion) -> dict:
    return {"tipo": "notificacion", "notificacion": {
        "id": aviso.id, "tipo": aviso.tipo, "titulo": aviso.titulo, "texto": aviso.texto,
        "enlace": aviso.enlace, "leida": False,
        "creado_en": aviso.creado_en.isoformat() if aviso.creado_en else None,
    }}


def pendientes(db: Session) -> List[tuple]:
    """Saca los avisos ya guardados: lista de (usuario_id, evento)."""
    avisos = db.info.pop(_CLAVE, [])
    return [(a.usuario_id, _evento(a)) for a in avisos if a.id is not None]


def despachar(db: Session) -> None:
    """Llamar DESPUÉS de db.commit(). Envía por WebSocket los avisos pendientes."""
    for usuario_id, evento in pendientes(db):
        gestor.enviar_desde_hilo([usuario_id], evento)
