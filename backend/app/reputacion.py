"""Cálculo de reputación: promedios de estrellas y reseñas (US-20, US-21, US-22)."""
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from . import schemas
from .models import Calificacion, Cochera, Reserva


def promedio_usuario(db: Session, usuario_id: int) -> Tuple[Optional[float], int]:
    """(promedio, total) de las calificaciones que recibió una persona."""
    prom, total = db.execute(
        select(func.avg(Calificacion.estrellas), func.count(Calificacion.id))
        .where(Calificacion.destinatario_id == usuario_id)
    ).one()
    return (round(float(prom), 1) if prom is not None else None), int(total)


def promedios_cocheras(db: Session, ids: Iterable[int]) -> Dict[int, Tuple[float, int]]:
    """Promedio de las calificaciones que los arrendatarios dieron en cada cochera."""
    ids = list(ids)
    if not ids:
        return {}
    filas = db.execute(
        select(Reserva.cochera_id, func.avg(Calificacion.estrellas), func.count(Calificacion.id))
        .join(Reserva, Reserva.id == Calificacion.reserva_id)
        .join(Cochera, Cochera.id == Reserva.cochera_id)
        .where(Reserva.cochera_id.in_(ids), Calificacion.destinatario_id == Cochera.arrendador_id)
        .group_by(Reserva.cochera_id)
    ).all()
    return {cid: (round(float(p), 1), int(n)) for cid, p, n in filas}


def _resena(c: Calificacion) -> schemas.ResenaSalida:
    return schemas.ResenaSalida(
        id=c.id, autor_id=c.autor_id, autor_nombre=c.autor.nombre, autor_foto=c.autor.foto_url,
        estrellas=c.estrellas, comentario=c.comentario,
        cochera_titulo=c.reserva.cochera.titulo if c.reserva and c.reserva.cochera else None,
        creado_en=c.creado_en,
    )


_CARGA = (selectinload(Calificacion.autor),
          selectinload(Calificacion.reserva).selectinload(Reserva.cochera))


def resenas_usuario(db: Session, usuario_id: int, limite: int = 20) -> List[schemas.ResenaSalida]:
    filas = db.scalars(
        select(Calificacion).where(Calificacion.destinatario_id == usuario_id)
        .options(*_CARGA).order_by(Calificacion.creado_en.desc()).limit(limite)
    ).all()
    return [_resena(c) for c in filas]


def resenas_cochera(db: Session, cochera: Cochera, limite: int = 20) -> List[schemas.ResenaSalida]:
    filas = db.scalars(
        select(Calificacion).join(Reserva, Reserva.id == Calificacion.reserva_id)
        .where(Reserva.cochera_id == cochera.id, Calificacion.destinatario_id == cochera.arrendador_id)
        .options(*_CARGA).order_by(Calificacion.creado_en.desc()).limit(limite)
    ).all()
    return [_resena(c) for c in filas]
