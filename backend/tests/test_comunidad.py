"""Calificaciones, filtros, perfil, recuperación, notificaciones y moderación.

US-03, US-04, US-10, US-12, US-15, US-20 a US-25.
"""
from sqlalchemy import text

from app.database import engine
from tests.conftest import PNG, proximo, publicar, registrar


def solicitar(cliente, cabeceras, cochera_id, inicio, fin):
    return cliente.post("/api/reservas", headers=cabeceras, json={
        "cochera_id": cochera_id, "inicio": inicio.isoformat(), "fin": fin.isoformat()})


def reserva_finalizada(cliente, escenario):
    """Solicita y confirma una reserva y la deja finalizada directamente en la base."""
    r = solicitar(cliente, escenario["cab_cliente"], escenario["cochera"]["id"], proximo(0, 10), proximo(0, 12))
    rid = r.json()["id"]
    assert cliente.post(f"/api/reservas/{rid}/confirmar", headers=escenario["cab_dueno"]).status_code == 200
    with engine.begin() as con:
        con.execute(text("UPDATE reserva SET estado='finalizada', salida_real=now() WHERE id=:i"), {"i": rid})
    return rid


def hacer_admin(cliente):
    cab, usuario = registrar(cliente, "arrendatario", "Ana Admin")
    with engine.begin() as con:
        con.execute(text("UPDATE usuario SET rol='administrador' WHERE id=:i"), {"i": usuario["id"]})
    return cab


# ------------------------------------------------------------ calificaciones
def test_ambas_partes_se_califican_una_sola_vez(cliente, escenario):
    rid = reserva_finalizada(cliente, escenario)
    reserva = cliente.get(f"/api/reservas/{rid}", headers=escenario["cab_cliente"]).json()
    assert reserva["puede_calificar"] is True

    r = cliente.post(f"/api/reservas/{rid}/calificar", headers=escenario["cab_cliente"],
                     json={"estrellas": 4, "comentario": "Muy buena"})
    assert r.status_code == 201, r.text
    assert cliente.post(f"/api/reservas/{rid}/calificar", headers=escenario["cab_cliente"],
                        json={"estrellas": 5}).status_code == 409
    assert cliente.post(f"/api/reservas/{rid}/calificar", headers=escenario["cab_dueno"],
                        json={"estrellas": 5}).status_code == 201

    reserva = cliente.get(f"/api/reservas/{rid}", headers=escenario["cab_cliente"]).json()
    assert reserva["puede_calificar"] is False and reserva["mi_calificacion"] == 4

    # La cochera y el perfil del dueño muestran la reputación
    cochera = cliente.get(f"/api/cocheras/{escenario['cochera']['id']}").json()
    assert cochera["calificacion"] == 4.0 and cochera["total_calificaciones"] == 1
    assert cochera["resenas"][0]["comentario"] == "Muy buena"
    perfil = cliente.get(f"/api/usuarios/{escenario['dueno']['id']}").json()
    assert perfil["calificacion_promedio"] == 4.0
    assert perfil["transacciones_completadas"] == 1
    assert len(perfil["cocheras"]) == 1
    conductor = cliente.get(f"/api/usuarios/{escenario['conductor']['id']}").json()
    assert conductor["calificacion_promedio"] == 5.0


def test_no_se_califica_una_reserva_no_finalizada_ni_ajena(cliente, escenario):
    r = solicitar(cliente, escenario["cab_cliente"], escenario["cochera"]["id"], proximo(0, 10), proximo(0, 12))
    rid = r.json()["id"]
    assert cliente.post(f"/api/reservas/{rid}/calificar", headers=escenario["cab_cliente"],
                        json={"estrellas": 5}).status_code == 409
    cab_otro, _ = registrar(cliente, "arrendatario", "Otro Mas")
    assert cliente.post(f"/api/reservas/{rid}/calificar", headers=cab_otro,
                        json={"estrellas": 5}).status_code == 403
    assert cliente.post(f"/api/reservas/{rid}/calificar", headers=escenario["cab_cliente"],
                        json={"estrellas": 6}).status_code == 422


# ------------------------------------------------------------------ filtros
def test_filtros_de_busqueda(cliente, escenario):
    base = "/api/cocheras/buscar?lat=-12.1211&lng=-77.0297&radio_km=5"
    publicar(cliente, escenario["cab_dueno"], titulo="Espacio para moto en Larco", tipo_vehiculo="moto",
             techada=False, precio_hora=3.0)

    assert len(cliente.get(base).json()) == 2
    assert [c["tipo_vehiculo"] for c in cliente.get(base + "&precio_max=4").json()] == ["moto"]
    assert [c["tipo_vehiculo"] for c in cliente.get(base + "&tipo_vehiculo=auto").json()] == ["auto"]
    assert len(cliente.get(base + "&tipo_vehiculo=moto").json()) == 2   # una moto cabe en ambas
    assert [c["techada"] for c in cliente.get(base + "&techada=false").json()] == [False]

    # Por horario: la del escenario solo abre de lunes a viernes
    lunes = f"&inicio={proximo(0, 10).isoformat()}&fin={proximo(0, 12).isoformat()}".replace("+", "%2B")
    domingo = f"&inicio={proximo(6, 10).isoformat()}&fin={proximo(6, 12).isoformat()}".replace("+", "%2B")
    resultado = cliente.get(base + "&tipo_vehiculo=auto" + lunes).json()
    assert len(resultado) == 1 and resultado[0]["costo_horario"] == 12.0
    assert cliente.get(base + "&tipo_vehiculo=auto" + domingo).json() == []
    assert cliente.get(base + "&inicio=" + proximo(0, 10).isoformat().replace("+", "%2B")).status_code == 422


# ----------------------------------------------------- perfil y contraseña
def test_perfil_vehiculos_y_cambio_de_contrasena(cliente, escenario):
    cab = escenario["cab_cliente"]
    r = cliente.put("/api/perfil", headers=cab, json={"nombre": "Luis Paredes", "telefono": "999 111 222"})
    assert r.status_code == 200 and r.json()["telefono"] == "999 111 222"
    r = cliente.post("/api/perfil/vehiculos", headers=cab, json={"placa": "abc-123", "tipo": "auto"})
    assert r.status_code == 201 and r.json()["vehiculos"][0]["placa"] == "ABC-123"
    assert cliente.post("/api/perfil/vehiculos", headers=cab,
                        json={"placa": "ABC-123", "tipo": "auto"}).status_code == 409
    vid = r.json()["vehiculos"][0]["id"]
    assert cliente.delete(f"/api/perfil/vehiculos/{vid}", headers=cab).json()["vehiculos"] == []

    assert cliente.post("/api/perfil/contrasena", headers=cab,
                        json={"actual": "mala", "nueva": "Nueva1234"}).status_code == 400
    assert cliente.post("/api/perfil/contrasena", headers=cab,
                        json={"actual": "Clave1234", "nueva": "Nueva1234"}).status_code == 204
    correo = escenario["conductor"]["correo"]
    assert cliente.post("/api/auth/login", json={"correo": correo, "contrasena": "Nueva1234"}).status_code == 200


def test_recuperar_contrasena_con_enlace_de_un_solo_uso(cliente, escenario):
    correo = escenario["conductor"]["correo"]
    r = cliente.post("/api/auth/recuperar", json={"correo": correo})
    assert r.status_code == 200
    token = r.json()["enlace_demo"].split("token=")[1]
    # Un correo que no existe recibe la misma respuesta
    otro = cliente.post("/api/auth/recuperar", json={"correo": "nadie@prueba.pe"}).json()
    assert otro["mensaje"] == r.json()["mensaje"] and otro["enlace_demo"] is None

    assert cliente.post("/api/auth/restablecer", json={"token": token, "contrasena": "Otra12345"}).status_code == 204
    assert cliente.post("/api/auth/restablecer", json={"token": token, "contrasena": "Otra12345"}).status_code == 400
    assert cliente.post("/api/auth/login", json={"correo": correo, "contrasena": "Otra12345"}).status_code == 200


def test_verificacion_de_identidad(cliente, escenario):
    cab, admin = escenario["cab_dueno"], hacer_admin(cliente)
    r = cliente.post("/api/perfil/documento", headers=cab, files={"documento": ("dni.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["verificacion"] == "pendiente"
    # el documento no es público: un usuario común no puede verlo
    uid = escenario["dueno"]["id"]
    assert cliente.get(f"/api/admin/verificaciones/{uid}/documento", headers=cab).status_code == 403
    assert cliente.get(f"/api/admin/verificaciones/{uid}/documento", headers=admin).status_code == 200
    assert [v["usuario_id"] for v in cliente.get("/api/admin/verificaciones", headers=admin).json()] == [uid]
    assert cliente.post(f"/api/admin/verificaciones/{uid}", headers=admin, json={"aprobar": True}).status_code == 204
    assert cliente.get(f"/api/usuarios/{uid}").json()["verificado"] is True
    # y le llega una notificación
    bandeja = cliente.get("/api/notificaciones", headers=cab).json()
    assert bandeja["sin_leer"] >= 1 and bandeja["notificaciones"][0]["titulo"] == "Identidad verificada"
    assert cliente.post("/api/notificaciones/leidas", headers=cab).status_code == 204
    assert cliente.get("/api/notificaciones", headers=cab).json()["sin_leer"] == 0


# --------------------------------------------------------------- moderación
def test_reporte_procedente_suspende_la_cochera(cliente, escenario):
    cid, admin = escenario["cochera"]["id"], hacer_admin(cliente)
    r = cliente.post(f"/api/cocheras/{cid}/reportes", headers=escenario["cab_cliente"],
                     json={"motivo": "fotos_enganosas", "detalle": "No es el mismo lugar"})
    assert r.status_code == 201
    assert cliente.post(f"/api/cocheras/{cid}/reportes", headers=escenario["cab_cliente"],
                        json={"motivo": "otro"}).status_code == 409
    assert cliente.post(f"/api/cocheras/{cid}/reportes", headers=escenario["cab_dueno"],
                        json={"motivo": "otro"}).status_code == 409
    assert cliente.get("/api/admin/reportes", headers=escenario["cab_cliente"]).status_code == 403

    pendientes = cliente.get("/api/admin/reportes", headers=admin).json()
    assert len(pendientes) == 1
    r = cliente.post(f"/api/admin/reportes/{pendientes[0]['id']}/resolver", headers=admin,
                     json={"decision": "procedente", "nota": "Fotos de otro lugar"})
    assert r.status_code == 200 and r.json()["cochera_suspendida"] is True

    # Ya no aparece en la búsqueda, no se puede reservar ni reactivar, y el público no la ve
    buscar = "/api/cocheras/buscar?lat=-12.1211&lng=-77.0297&radio_km=5"
    assert cliente.get(buscar).json() == []
    assert cliente.get(f"/api/cocheras/{cid}").status_code == 404
    assert cliente.get(f"/api/cocheras/{cid}", headers=escenario["cab_dueno"]).json()["suspendida"] is True
    assert solicitar(cliente, escenario["cab_cliente"], cid, proximo(0, 10), proximo(0, 12)).status_code == 409
    assert cliente.patch(f"/api/cocheras/{cid}/estado", headers=escenario["cab_dueno"],
                         json={"activa": True}).status_code == 409
    assert cliente.get("/api/admin/resumen", headers=admin).json()["cocheras_suspendidas"] == 1

    assert cliente.post(f"/api/admin/cocheras/{cid}/reactivar", headers=admin).status_code == 204
    assert len(cliente.get(buscar).json()) == 1


def test_disputa_con_reembolso(cliente, escenario):
    admin = hacer_admin(cliente)
    r = solicitar(cliente, escenario["cab_cliente"], escenario["cochera"]["id"], proximo(0, 10), proximo(0, 12))
    rid = r.json()["id"]
    # no se abre disputa sobre una solicitud sin confirmar
    assert cliente.post(f"/api/reservas/{rid}/disputas", headers=escenario["cab_cliente"],
                        json={"tipo": "reserva", "descripcion": "Quiero reclamar algo importante"}).status_code == 409
    cliente.post(f"/api/reservas/{rid}/confirmar", headers=escenario["cab_dueno"])
    cliente.post(f"/api/pagos/{rid}/recibido", json={"medio": "efectivo"}, headers=escenario["cab_dueno"])

    r = cliente.post(f"/api/reservas/{rid}/disputas", headers=escenario["cab_cliente"],
                     json={"tipo": "pago", "descripcion": "Pagué pero el portón no abría."})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    assert cliente.post(f"/api/reservas/{rid}/disputas", headers=escenario["cab_dueno"],
                        json={"tipo": "pago", "descripcion": "Otra disputa sobre lo mismo"}).status_code == 409
    assert cliente.get(f"/api/reservas/{rid}", headers=escenario["cab_dueno"]).json()["disputa_abierta"] is True
    assert len(cliente.get("/api/disputas/mias", headers=escenario["cab_dueno"]).json()) == 1

    r = cliente.post(f"/api/admin/disputas/{did}/resolver", headers=admin,
                     json={"accion": "reembolso", "resolucion": "Se comprobó la falla del portón."})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "resuelta" and r.json()["estado_pago"] == "por_devolver"
    assert cliente.post(f"/api/admin/disputas/{did}/resolver", headers=admin,
                        json={"accion": "sin_accion", "resolucion": "Otra vez lo mismo"}).status_code == 409
