"""Chat en tiempo real (US-13)."""
from tests.conftest import registrar


def token(cabeceras):
    return cabeceras["Authorization"].split()[1]


def test_conversacion_por_http(cliente, escenario):
    cid, cab_cliente, cab_dueno = escenario["cochera"]["id"], escenario["cab_cliente"], escenario["cab_dueno"]

    conv = cliente.post("/api/conversaciones", json={"cochera_id": cid}, headers=cab_cliente).json()
    assert conv["otro_nombre"] == "Rosa Dueña"
    # abrirla otra vez devuelve la misma
    assert cliente.post("/api/conversaciones", json={"cochera_id": cid}, headers=cab_cliente).json()["id"] == conv["id"]

    r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json={"texto": "  ¿Entra una camioneta?  "},
                     headers=cab_cliente)
    assert r.status_code == 201 and r.json()["texto"] == "¿Entra una camioneta?"

    # el arrendador ve la conversación con un mensaje sin leer
    lista = cliente.get("/api/conversaciones", headers=cab_dueno).json()
    assert lista[0]["sin_leer"] == 1 and lista[0]["ultimo_mensaje"] == "¿Entra una camioneta?"
    assert lista[0]["otro_nombre"] == "Luis Conductor"

    # al abrirla queda leída
    mensajes = cliente.get(f"/api/conversaciones/{conv['id']}/mensajes", headers=cab_dueno).json()
    assert len(mensajes) == 1
    assert cliente.get("/api/conversaciones", headers=cab_dueno).json()[0]["sin_leer"] == 0


def test_un_tercero_no_entra_a_la_conversacion(cliente, escenario):
    conv = cliente.post("/api/conversaciones", json={"cochera_id": escenario["cochera"]["id"]},
                        headers=escenario["cab_cliente"]).json()
    cab_intruso, _ = registrar(cliente, "arrendatario", "Pedro Intruso")
    assert cliente.get(f"/api/conversaciones/{conv['id']}/mensajes", headers=cab_intruso).status_code == 403
    r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json={"texto": "hola"}, headers=cab_intruso)
    assert r.status_code == 403


def test_no_acepta_mensajes_vacios(cliente, escenario):
    conv = cliente.post("/api/conversaciones", json={"cochera_id": escenario["cochera"]["id"]},
                        headers=escenario["cab_cliente"]).json()
    r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json={"texto": "   "},
                     headers=escenario["cab_cliente"])
    assert r.status_code == 422


def test_mensajes_en_tiempo_real_por_websocket(cliente, escenario):
    cab_cliente, cab_dueno = escenario["cab_cliente"], escenario["cab_dueno"]
    conv = cliente.post("/api/conversaciones", json={"cochera_id": escenario["cochera"]["id"]},
                        headers=cab_cliente).json()

    with cliente.websocket_connect(f"/ws?token={token(cab_cliente)}") as ws_cliente, \
         cliente.websocket_connect(f"/ws?token={token(cab_dueno)}") as ws_dueno:
        ws_cliente.send_json({"tipo": "mensaje", "conversacion_id": conv["id"], "texto": "Hola, ¿está libre hoy?"})

        recibido = ws_dueno.receive_json()
        assert recibido["tipo"] == "mensaje"
        assert recibido["mensaje"]["texto"] == "Hola, ¿está libre hoy?"
        assert recibido["mensaje"]["emisor_id"] == escenario["conductor"]["id"]
        # quien envía también recibe la confirmación
        assert ws_cliente.receive_json()["mensaje"]["id"] == recibido["mensaje"]["id"]

        ws_dueno.send_json({"tipo": "mensaje", "conversacion_id": conv["id"], "texto": "Sí, desde las 10."})
        assert ws_cliente.receive_json()["mensaje"]["texto"] == "Sí, desde las 10."

    # los mensajes quedaron guardados
    historial = cliente.get(f"/api/conversaciones/{conv['id']}/mensajes", headers=cab_cliente).json()
    assert [m["texto"] for m in historial] == ["Hola, ¿está libre hoy?", "Sí, desde las 10."]


def test_el_websocket_avisa_de_los_cambios_de_reserva(cliente, escenario):
    from tests.conftest import proximo
    cab_cliente, cab_dueno = escenario["cab_cliente"], escenario["cab_dueno"]
    with cliente.websocket_connect(f"/ws?token={token(cab_dueno)}") as ws_dueno:
        r = cliente.post("/api/reservas", headers=cab_cliente, json={
            "cochera_id": escenario["cochera"]["id"],
            "inicio": proximo(0, 10).isoformat(), "fin": proximo(0, 12).isoformat()})
        assert r.status_code == 201
        aviso = ws_dueno.receive_json()
        assert aviso["tipo"] == "reserva" and aviso["evento"] == "solicitada"


def test_el_websocket_rechaza_un_token_invalido(cliente):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with cliente.websocket_connect("/ws?token=falso") as ws:
            ws.receive_json()
