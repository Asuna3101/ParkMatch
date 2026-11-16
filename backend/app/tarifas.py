"""Reglas de negocio del calendario, de las tarifas y de la penalización.

Son funciones puras: no tocan la base de datos, así que se prueban solas.
Trabajan con minutos del día (0 a 1440) en la hora local de la cochera.
"""
import math
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, List, Optional, Sequence, Tuple

from . import config

MINUTOS_DIA = 24 * 60
DURACION_MINIMA = 30  # minutos

Franja = Tuple[int, int]  # (minuto_inicio, minuto_fin)


def a_minutos(hora: time) -> int:
    """Minutos desde medianoche. 23:59 representa el final del día."""
    minutos = hora.hour * 60 + hora.minute
    return MINUTOS_DIA if minutos >= MINUTOS_DIA - 1 else minutos


def a_local(momento: datetime) -> datetime:
    """Convierte a la zona horaria configurada (por defecto, Lima)."""
    if momento.tzinfo is None:
        return momento.replace(tzinfo=config.ZONA)
    return momento.astimezone(config.ZONA)


def hay_solape(franjas: Iterable[Franja]) -> bool:
    """True si dos franjas de la misma lista se cruzan."""
    ordenadas = sorted(franjas)
    return any(a[1] > b[0] for a, b in zip(ordenadas, ordenadas[1:]))


def unir_franjas(franjas: Iterable[Franja]) -> List[Franja]:
    """Une franjas contiguas: 08–12 y 12–18 pasan a ser 08–18."""
    unidas: List[Franja] = []
    for inicio, fin in sorted(franjas):
        if unidas and inicio <= unidas[-1][1]:
            unidas[-1] = (unidas[-1][0], max(unidas[-1][1], fin))
        else:
            unidas.append((inicio, fin))
    return unidas


def validar_horario(inicio: datetime, fin: datetime, ahora: Optional[datetime] = None) -> Optional[str]:
    """Reglas generales de una reserva. Devuelve el motivo si no es válida."""
    inicio_l, fin_l = a_local(inicio), a_local(fin)
    ahora_l = a_local(ahora or datetime.now(config.ZONA))
    if fin_l <= inicio_l:
        return "La hora de salida debe ser posterior a la de ingreso."
    if inicio_l < ahora_l:
        return "El horario elegido ya pasó."
    if inicio_l.date() != fin_l.date():
        return "La reserva debe empezar y terminar el mismo día."
    if (fin_l - inicio_l).total_seconds() < DURACION_MINIMA * 60:
        return f"La reserva mínima es de {DURACION_MINIMA} minutos."
    return None


def dentro_de_disponibilidad(
    inicio: datetime,
    fin: datetime,
    disponibilidades: Sequence,
) -> bool:
    """¿El horario cae dentro del calendario semanal del arrendador? (requisito 10)"""
    inicio_l, fin_l = a_local(inicio), a_local(fin)
    dia = inicio_l.weekday()  # 0 = lunes
    desde = inicio_l.hour * 60 + inicio_l.minute
    hasta = a_minutos(fin_l.time())
    del_dia = [
        (a_minutos(d.hora_inicio), a_minutos(d.hora_fin))
        for d in disponibilidades
        if d.dia_semana == dia
    ]
    return any(ini <= desde and hasta <= fin_ for ini, fin_ in unir_franjas(del_dia))


def calcular_costo(
    inicio: datetime,
    fin: datetime,
    precio_base: Decimal,
    tarifas: Sequence,
) -> Decimal:
    """Costo de la reserva (requisito 23).

    Cada minuto se cobra con la tarifa de la franja en la que cae; los
    minutos fuera de toda franja se cobran con el precio base.
    """
    inicio_l, fin_l = a_local(inicio), a_local(fin)
    desde = inicio_l.hour * 60 + inicio_l.minute
    hasta = a_minutos(fin_l.time())
    total = hasta - desde

    costo = Decimal("0")
    cubiertos = 0
    for tarifa in tarifas:
        t_ini, t_fin = a_minutos(tarifa.hora_inicio), a_minutos(tarifa.hora_fin)
        minutos = max(0, min(hasta, t_fin) - max(desde, t_ini))
        costo += Decimal(minutos) * Decimal(tarifa.precio_hora) / Decimal(60)
        cubiertos += minutos

    costo += Decimal(total - cubiertos) * Decimal(precio_base) / Decimal(60)
    return costo.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calcular_exceso(fin: datetime, salida: datetime, precio_hora: Decimal) -> Tuple[int, Decimal, Decimal]:
    """Uso más allá de la hora reservada (requisito 26 · US-19).

    Devuelve (minutos de exceso, cargo por el tiempo adicional, penalización).
      · El tiempo adicional se cobra al precio por hora, por minuto.
      · La penalización es el 10 % del precio por hora, prorrateado por minuto.
    Ejemplo: S/ 6 la hora y 30 minutos de exceso → S/ 3.00 de tiempo adicional
    y S/ 0.30 de penalización.
    """
    segundos = (salida - fin).total_seconds()
    if segundos <= 0:
        return 0, Decimal("0.00"), Decimal("0.00")
    minutos = math.ceil(segundos / 60)
    centavos = Decimal("0.01")
    cargo = (Decimal(minutos) * Decimal(precio_hora) / Decimal(60)).quantize(centavos, rounding=ROUND_HALF_UP)
    penalizacion = (Decimal(minutos) * Decimal(precio_hora) * Decimal(config.PENALIZACION_PORCENTAJE)
                    / Decimal(100) / Decimal(60)).quantize(centavos, rounding=ROUND_HALF_UP)
    return minutos, cargo, penalizacion
