"""Riesgo R-01: dos personas no pueden reservar el mismo horario.

Se prueban las dos barreras por separado:
  1. La API, con varias confirmaciones lanzadas exactamente al mismo tiempo.
  2. La base de datos sola, saltándose la aplicación.
"""
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import engine
from app.main import app
from tests.conftest import proximo, registrar

SIMULTANEAS = 8


def test_confirmaciones_simultaneas_solo_una_gana(cliente, escenario):
    cid, cab_dueno = escenario["cochera"]["id"], escenario["cab_dueno"]

    # ocho arrendatarios piden horarios que se cruzan entre sí
    reservas = []
    for i in range(SIMULTANEAS):
        cab, _ = registrar(cliente, "arrendatario", f"Conductor {i}")
        r = cliente.post("/api/reservas", headers=cab, json={
            "cochera_id": cid, "inicio": proximo(0, 10).isoformat(), "fin": proximo(0, 12).isoformat()})
        assert r.status_code == 201
        reservas.append(r.json()["id"])

    # el arrendador confirma las ocho a la vez
    salida = threading.Barrier(SIMULTANEAS)
    codigos = []

    def confirmar(reserva_id):
        with TestClient(app) as c:
            salida.wait()
            codigos.append(c.post(f"/api/reservas/{reserva_id}/confirmar", headers=cab_dueno).status_code)

    hilos = [threading.Thread(target=confirmar, args=(rid,)) for rid in reservas]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert sorted(codigos) == [200] + [409] * (SIMULTANEAS - 1)

    with engine.connect() as con:
        confirmadas = con.execute(text(
            "SELECT count(*) FROM reserva WHERE cochera_id = :c AND estado = 'confirmada'"), {"c": cid}).scalar_one()
        pagos = con.execute(text("SELECT count(*) FROM pago")).scalar_one()
    assert confirmadas == 1
    assert pagos == 1


def test_la_base_de_datos_rechaza_el_cruce_por_si_sola(cliente, escenario):
    """Aunque la aplicación fallara, la restricción reserva_sin_solape protege los datos."""
    cid, uid = escenario["cochera"]["id"], escenario["conductor"]["id"]
    insertar = text("""
        INSERT INTO reserva (cochera_id, arrendatario_id, inicio, fin, estado, costo_total)
        VALUES (:c, :u, :i, :f, 'confirmada', 10)""")

    with engine.begin() as con:
        con.execute(insertar, {"c": cid, "u": uid, "i": proximo(0, 10), "f": proximo(0, 12)})

    with pytest.raises(IntegrityError) as error:
        with engine.begin() as con:
            con.execute(insertar, {"c": cid, "u": uid, "i": proximo(0, 11), "f": proximo(0, 13)})
    assert "reserva_sin_solape" in str(error.value)

    # un horario contiguo y uno en otra cochera sí entran
    with engine.begin() as con:
        con.execute(insertar, {"c": cid, "u": uid, "i": proximo(0, 12), "f": proximo(0, 14)})


def test_las_solicitudes_pendientes_si_pueden_cruzarse(cliente, escenario):
    """La restricción solo aplica a las confirmadas: varias personas pueden pedir el mismo horario."""
    cid = escenario["cochera"]["id"]
    for i in range(3):
        cab, _ = registrar(cliente, "arrendatario", f"Interesado {i}")
        r = cliente.post("/api/reservas", headers=cab, json={
            "cochera_id": cid, "inicio": proximo(0, 10).isoformat(), "fin": proximo(0, 12).isoformat()})
        assert r.status_code == 201
