"""Flujo de reserva y pago (US-08, US-16, US-17, US-18 y requisito 24)."""
from tests.conftest import proximo, registrar


def solicitar(cliente, cabeceras, cochera_id, inicio, fin):
    return cliente.post("/api/reservas", headers=cabeceras, json={
        "cochera_id": cochera_id, "inicio": inicio.isoformat(), "fin": fin.isoformat()})


def test_flujo_completo_del_mvp(cliente, escenario):
    cid = escenario["cochera"]["id"]
    cab_cliente, cab_dueno = escenario["cab_cliente"], escenario["cab_dueno"]

    # 1. el arrendatario solicita lunes de 10:00 a 12:00
    r = solicitar(cliente, cab_cliente, cid, proximo(0, 10), proximo(0, 12))
    assert r.status_code == 201, r.text
    reserva = r.json()
    assert reserva["estado"] == "solicitada"
    assert reserva["costo_total"] == 12.0
    assert reserva["pago"] is None

    # 2. el arrendador la ve entre sus solicitudes y la confirma
    recibidas = cliente.get("/api/reservas/recibidas", headers=cab_dueno).json()
    assert [x["id"] for x in recibidas] == [reserva["id"]]
    r = cliente.post(f"/api/reservas/{reserva['id']}/confirmar", headers=cab_dueno)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "confirmada"
    assert r.json()["pago"]["estado"] == "pendiente"
    assert r.json()["pago"]["monto"] == 12.0

    # 3. el horario queda bloqueado en la ficha de la cochera
    detalle = cliente.get(f"/api/cocheras/{cid}").json()
    assert len(detalle["ocupado"]) == 1

    # 4. el arrendador registra el pago recibido fuera de la aplicación
    r = cliente.post(f"/api/pagos/{reserva['id']}/recibido", json={"medio": "billetera"}, headers=cab_dueno)
    assert r.status_code == 200, r.text
    assert r.json()["pago"]["estado"] == "pagado"
    assert r.json()["pago"]["medio"] == "billetera"
    assert r.json()["pago"]["pagado_en"]
    assert r.json()["pago"]["comprobante_numero"].startswith("PM-")

    # 5. todo queda en el log de auditoría
    acciones = [x["accion"] for x in cliente.get("/api/auditoria", headers=cab_dueno).json()]
    for esperada in ("cochera_publicada", "reserva_solicitada", "reserva_confirmada", "pago_recibido"):
        assert esperada in acciones
    pago = next(x for x in cliente.get("/api/auditoria", headers=cab_dueno).json() if x["accion"] == "pago_recibido")
    assert pago["detalle"]["monto"] == 12.0 and pago["detalle"]["medio"] == "billetera"


def test_no_se_puede_reservar_fuera_del_calendario(cliente, escenario):
    r = solicitar(cliente, escenario["cab_cliente"], escenario["cochera"]["id"], proximo(5, 10), proximo(5, 12))
    assert r.status_code == 409
    r = solicitar(cliente, escenario["cab_cliente"], escenario["cochera"]["id"], proximo(0, 6), proximo(0, 9))
    assert r.status_code == 409


def test_no_se_puede_solicitar_un_horario_ya_confirmado(cliente, escenario):
    cid, cab_dueno = escenario["cochera"]["id"], escenario["cab_dueno"]
    primera = solicitar(cliente, escenario["cab_cliente"], cid, proximo(0, 10), proximo(0, 12)).json()
    cliente.post(f"/api/reservas/{primera['id']}/confirmar", headers=cab_dueno)

    cab_otro, _ = registrar(cliente, "arrendatario", "Marta Otra")
    cruzada = solicitar(cliente, cab_otro, cid, proximo(0, 11), proximo(0, 13))
    assert cruzada.status_code == 409
    assert "ya está reservado" in cruzada.json()["detail"]
    # un horario contiguo sí se puede: 12:00 es la salida del primero y el ingreso del segundo
    contigua = solicitar(cliente, cab_otro, cid, proximo(0, 12), proximo(0, 14))
    assert contigua.status_code == 201


def test_al_confirmar_se_rechazan_las_solicitudes_que_se_cruzan(cliente, escenario):
    cid, cab_dueno = escenario["cochera"]["id"], escenario["cab_dueno"]
    cab_otro, _ = registrar(cliente, "arrendatario", "Marta Otra")
    a = solicitar(cliente, escenario["cab_cliente"], cid, proximo(0, 10), proximo(0, 12)).json()
    b = solicitar(cliente, cab_otro, cid, proximo(0, 11), proximo(0, 13)).json()

    assert cliente.post(f"/api/reservas/{a['id']}/confirmar", headers=cab_dueno).status_code == 200
    mias = cliente.get("/api/reservas/mias", headers=cab_otro).json()
    assert mias[0]["id"] == b["id"] and mias[0]["estado"] == "rechazada"
    # y ya no se puede confirmar la segunda
    assert cliente.post(f"/api/reservas/{b['id']}/confirmar", headers=cab_dueno).status_code == 409


def test_rechazar_con_motivo(cliente, escenario):
    cid = escenario["cochera"]["id"]
    reserva = solicitar(cliente, escenario["cab_cliente"], cid, proximo(0, 10), proximo(0, 12)).json()
    r = cliente.post(f"/api/reservas/{reserva['id']}/rechazar", json={"motivo": "Ese día uso la cochera"},
                     headers=escenario["cab_dueno"])
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazada" and r.json()["motivo_rechazo"] == "Ese día uso la cochera"


def test_cancelar_libera_el_horario(cliente, escenario):
    cid, cab_cliente, cab_dueno = escenario["cochera"]["id"], escenario["cab_cliente"], escenario["cab_dueno"]
    reserva = solicitar(cliente, cab_cliente, cid, proximo(0, 10), proximo(0, 12)).json()
    cliente.post(f"/api/reservas/{reserva['id']}/confirmar", headers=cab_dueno)
    r = cliente.post(f"/api/reservas/{reserva['id']}/cancelar", headers=cab_cliente)
    assert r.status_code == 200 and r.json()["estado"] == "cancelada" and r.json()["pago"] is None
    # el mismo horario vuelve a estar disponible
    assert solicitar(cliente, cab_cliente, cid, proximo(0, 10), proximo(0, 12)).status_code == 201


def test_cancelar_con_pago_registrado_lo_deja_por_devolver(cliente, escenario):
    cid, cab_cliente, cab_dueno = escenario["cochera"]["id"], escenario["cab_cliente"], escenario["cab_dueno"]
    reserva = solicitar(cliente, cab_cliente, cid, proximo(0, 10), proximo(0, 12)).json()
    cliente.post(f"/api/reservas/{reserva['id']}/confirmar", headers=cab_dueno)
    cliente.post(f"/api/pagos/{reserva['id']}/recibido", json={"medio": "efectivo"}, headers=cab_dueno)
    r = cliente.post(f"/api/reservas/{reserva['id']}/cancelar", headers=cab_cliente)
    assert r.status_code == 200
    assert r.json()["pago"]["estado"] == "por_devolver"
    assert cliente.post(f"/api/pagos/{reserva['id']}/devuelto", headers=cab_dueno).json()["pago"]["estado"] == "reembolsado"


def test_permisos_sobre_reservas_y_pagos(cliente, escenario):
    cid, cab_cliente = escenario["cochera"]["id"], escenario["cab_cliente"]
    reserva = solicitar(cliente, cab_cliente, cid, proximo(0, 10), proximo(0, 12)).json()
    cab_intruso, _ = registrar(cliente, "arrendador", "Pedro Intruso")

    # un arrendatario no confirma; otro arrendador tampoco
    assert cliente.post(f"/api/reservas/{reserva['id']}/confirmar", headers=cab_cliente).status_code == 403
    assert cliente.post(f"/api/reservas/{reserva['id']}/confirmar", headers=cab_intruso).status_code == 403
    # el dueño no solicita reservas
    assert solicitar(cliente, escenario["cab_dueno"], cid, proximo(1, 10), proximo(1, 12)).status_code == 403
    # no se registra el pago de una reserva sin confirmar
    r = cliente.post(f"/api/pagos/{reserva['id']}/recibido", json={"medio": "efectivo"}, headers=escenario["cab_dueno"])
    assert r.status_code == 409
    # el intruso no ve la auditoría ajena
    assert all(x["accion"] == "usuario_registrado" for x in cliente.get("/api/auditoria", headers=cab_intruso).json())


def test_no_se_duplica_la_misma_solicitud(cliente, escenario):
    cid, cab = escenario["cochera"]["id"], escenario["cab_cliente"]
    assert solicitar(cliente, cab, cid, proximo(0, 10), proximo(0, 12)).status_code == 201
    assert solicitar(cliente, cab, cid, proximo(0, 10), proximo(0, 12)).status_code == 409
