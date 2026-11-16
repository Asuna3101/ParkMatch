"""Evaluación de un horario contra el calendario y las reservas vigentes."""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import tarifas
from .models import Cochera, Reserva


# Estados en los que una reserva ocupa el espacio.
VIGENTES = ("confirmada", "en_curso")


def hay_reserva_confirmada(db: Session, cochera_id: int, inicio: datetime, fin: datetime,
                           excluir_id: Optional[int] = None) -> bool:
    """¿Existe una reserva vigente que se cruce con [inicio, fin)?"""
    consulta = select(Reserva.id).where(
        Reserva.cochera_id == cochera_id,
        Reserva.estado.in_(VIGENTES),
        Reserva.inicio < fin,
        Reserva.fin > inicio,
    )
    if excluir_id is not None:
        consulta = consulta.where(Reserva.id != excluir_id)
    return db.scalar(consulta.limit(1)) is not None


def evaluar(db: Session, cochera: Cochera, inicio: datetime, fin: datetime
            ) -> Tuple[Optional[str], Decimal, int]:
    """Devuelve (motivo, costo, minutos). Si motivo es None, el horario se puede reservar."""
    motivo = tarifas.validar_horario(inicio, fin)
    if motivo:
        return motivo, Decimal("0"), 0

    costo = tarifas.calcular_costo(inicio, fin, cochera.precio_hora, cochera.tarifas)
    inicio_l, fin_l = tarifas.a_local(inicio), tarifas.a_local(fin)
    minutos = tarifas.a_minutos(fin_l.time()) - (inicio_l.hour * 60 + inicio_l.minute)

    if not cochera.activa or cochera.suspendida:
        return "Esta cochera no está recibiendo reservas.", costo, minutos
    if not tarifas.dentro_de_disponibilidad(inicio, fin, cochera.disponibilidades):
        return "La cochera no está disponible en ese horario.", costo, minutos
    if hay_reserva_confirmada(db, cochera.id, inicio, fin):
        return "Ese horario ya está reservado.", costo, minutos
    return None, costo, minutos
