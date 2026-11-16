"""Reglas puras de calendario y tarifas (requisitos 10 y 23)."""
from datetime import datetime, time
from decimal import Decimal
from types import SimpleNamespace as NS

from app import config, tarifas

LUNES = datetime(2030, 1, 7, tzinfo=config.ZONA)  # 7 de enero de 2030 es lunes


def a_las(hora, minuto=0):
    return LUNES.replace(hour=hora, minute=minuto)


def franja(dia, ini, fin):
    return NS(dia_semana=dia, hora_inicio=time(ini), hora_fin=time(fin))


def test_costo_con_precio_base():
    assert tarifas.calcular_costo(a_las(10), a_las(13), Decimal("6"), []) == Decimal("18.00")


def test_costo_prorratea_por_minuto():
    assert tarifas.calcular_costo(a_las(10), a_las(10, 45), Decimal("6"), []) == Decimal("4.50")


def test_costo_mezcla_base_y_franja():
    # 17:00–18:00 a S/ 6 y 18:00–20:00 a S/ 9
    noche = [NS(hora_inicio=time(18), hora_fin=time(22), precio_hora=Decimal("9"))]
    assert tarifas.calcular_costo(a_las(17), a_las(20), Decimal("6"), noche) == Decimal("24.00")


def test_costo_hasta_el_final_del_dia():
    # 23:59 representa la medianoche: de 22:00 a 24:00 son dos horas
    fin = LUNES.replace(hour=23, minute=59)
    assert tarifas.calcular_costo(a_las(22), fin, Decimal("5"), []) == Decimal("10.00")


def test_disponibilidad_dentro_y_fuera():
    calendario = [franja(0, 8, 12)]
    assert tarifas.dentro_de_disponibilidad(a_las(9), a_las(11), calendario)
    assert not tarifas.dentro_de_disponibilidad(a_las(11), a_las(13), calendario)
    assert not tarifas.dentro_de_disponibilidad(a_las(7), a_las(9), calendario)


def test_disponibilidad_respeta_el_dia_de_la_semana():
    solo_martes = [franja(1, 8, 20)]
    assert not tarifas.dentro_de_disponibilidad(a_las(9), a_las(11), solo_martes)


def test_franjas_contiguas_se_unen():
    calendario = [franja(0, 8, 12), franja(0, 12, 18)]
    assert tarifas.dentro_de_disponibilidad(a_las(11), a_las(13), calendario)
    assert tarifas.unir_franjas([(480, 720), (720, 1080)]) == [(480, 1080)]


def test_detecta_franjas_que_se_cruzan():
    assert tarifas.hay_solape([(480, 720), (700, 900)])
    assert not tarifas.hay_solape([(480, 720), (720, 900)])


def test_validar_horario():
    ahora = a_las(8)
    assert tarifas.validar_horario(a_las(10), a_las(12), ahora) is None
    assert "posterior" in tarifas.validar_horario(a_las(12), a_las(10), ahora)
    assert "ya pasó" in tarifas.validar_horario(a_las(6), a_las(7), ahora)
    assert "mínima" in tarifas.validar_horario(a_las(10), a_las(10, 15), ahora)
    manana = a_las(10).replace(day=8)
    assert "mismo día" in tarifas.validar_horario(a_las(22), manana, ahora)
