"""Registro e inicio de sesión (US-01, US-02)."""
from sqlalchemy import text

from app.database import engine
from tests.conftest import registrar

VALIDO = {"nombre": "Ana Torres", "correo": "ana@prueba.pe", "contrasena": "Clave1234", "rol": "arrendador"}


def test_registro_devuelve_token_y_usuario(cliente):
    r = cliente.post("/api/auth/registro", json=VALIDO)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["token"]
    assert cuerpo["usuario"]["rol"] == "arrendador"
    assert "contrasena" not in str(cuerpo)


def test_la_contrasena_se_guarda_cifrada_con_bcrypt(cliente):
    cliente.post("/api/auth/registro", json=VALIDO)
    with engine.connect() as con:
        guardada = con.execute(text("SELECT contrasena_hash FROM usuario")).scalar_one()
    assert guardada != VALIDO["contrasena"]
    assert guardada.startswith("$2")


def test_no_permite_dos_cuentas_con_el_mismo_correo(cliente):
    cliente.post("/api/auth/registro", json=VALIDO)
    r = cliente.post("/api/auth/registro", json={**VALIDO, "correo": "ANA@prueba.pe"})
    assert r.status_code == 409


def test_rechaza_contrasena_debil(cliente):
    r = cliente.post("/api/auth/registro", json={**VALIDO, "contrasena": "solotexto"})
    assert r.status_code == 422
    assert "letras y números" in r.json()["detail"]
    r = cliente.post("/api/auth/registro", json={**VALIDO, "contrasena": "a1"})
    assert r.status_code == 422


def test_rechaza_correo_invalido_con_mensaje_claro(cliente):
    r = cliente.post("/api/auth/registro", json={**VALIDO, "correo": "no-es-correo"})
    assert r.status_code == 422
    assert "correo válido" in r.json()["detail"]


def test_no_se_puede_registrar_un_administrador(cliente):
    r = cliente.post("/api/auth/registro", json={**VALIDO, "rol": "administrador"})
    assert r.status_code == 422


def test_login_correcto_e_incorrecto(cliente):
    cliente.post("/api/auth/registro", json=VALIDO)
    bien = cliente.post("/api/auth/login", json={"correo": "ana@prueba.pe", "contrasena": "Clave1234"})
    assert bien.status_code == 200 and bien.json()["token"]
    mal = cliente.post("/api/auth/login", json={"correo": "ana@prueba.pe", "contrasena": "otra12345"})
    assert mal.status_code == 401
    nadie = cliente.post("/api/auth/login", json={"correo": "nadie@prueba.pe", "contrasena": "Clave1234"})
    assert nadie.status_code == 401
    assert mal.json()["detail"] == nadie.json()["detail"]  # no revela si el correo existe


def test_perfil_exige_token_valido(cliente):
    assert cliente.get("/api/auth/yo").status_code == 401
    assert cliente.get("/api/auth/yo", headers={"Authorization": "Bearer falso"}).status_code == 401
    cabeceras, usuario = registrar(cliente, "arrendatario")
    r = cliente.get("/api/auth/yo", headers=cabeceras)
    assert r.status_code == 200 and r.json()["id"] == usuario["id"]
