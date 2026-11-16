"""Log de auditoría (requisitos 50 y 57)."""
from typing import Optional

from sqlalchemy.orm import Session

from .models import LogAuditoria


def registrar(
    db: Session,
    usuario_id: Optional[int],
    accion: str,
    entidad: str,
    entidad_id: Optional[int] = None,
    **detalle,
) -> None:
    """Agrega un registro a la misma transacción que la operación auditada.

    Así el log y el cambio se guardan juntos o no se guarda ninguno.
    """
    db.add(LogAuditoria(
        usuario_id=usuario_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        detalle=detalle,
    ))
