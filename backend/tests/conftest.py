"""Preparación de las pruebas.

Usan una base de datos aparte (parkmatch_test) para no tocar los datos reales.
Antes de correrlas crea esa base una sola vez:   CREATE DATABASE parkmatch_test;
"""
import os
import re
import tempfile
from datetime import datetime, time, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# La URL de pruebas se deriva de la del .env cambiando el nombre de la base.
from dotenv import dotenv_values  # noqa: E402

_url = os.getenv("DATABASE_URL") or dotenv_values(RAIZ / ".env").get("DATABASE_URL", "")
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL") or re.sub(r"/[^/]+$", "/parkmatch_test", _url)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import config  # noqa: E402

config.CARPETA_UPLOADS = Path(tempfile.mkdtemp(prefix="parkmatch_uploads_"))

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402

TABLAS = ("log_auditoria, mensaje, conversacion, pago, reserva, disponibilidad, "
          "tarifa, foto_cochera, ubicacion, cochera, usuario")

# PNG válido de 1×1 píxel
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


@pytest.fixture(scope="session", autouse=True)
def esquema():
    # Se ejecuta por el cursor DBAPI: exec_driver_sql sin parámetros falla con psycopg2 reciente.
    conexion = engine.raw_connection()
    try:
        cursor = conexion.cursor()
        cursor.execute((RAIZ / "db" / "schema.sql").read_text(encoding="utf-8"))
        conexion.commit()
    finally:
        conexion.close()
    yield


@pytest.fixture(autouse=True)
def limpiar(esquema):
    with engine.begin() as con:
        con.execute(text(f"TRUNCATE {TABLAS} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ ayudantes
def registrar(cliente, rol, nombre=None, correo=None):
    nombre = nombre or f"Persona {rol}"
    correo = correo or f"{nombre.lower().replace(' ', '.')}@prueba.pe"
    r = cliente.post("/api/auth/registro", json={
        "nombre": nombre, "correo": correo, "contrasena": "Clave1234", "rol": rol})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["usuario"]


def proximo(dia_semana: int, hora: int, minuto: int = 0) -> datetime:
    """Próxima fecha (a partir de mañana) que cae en ese día de la semana, hora de Lima."""
    hoy = datetime.now(config.ZONA).date()
    dias = (dia_semana - hoy.weekday() - 1) % 7 + 1
    return datetime.combine(hoy + timedelta(days=dias), time(hora, minuto), tzinfo=config.ZONA)


DATOS_COCHERA = {
    "titulo": "Cochera techada en Miraflores",
    "descripcion": "Espacio amplio y seguro, con portón eléctrico y vigilancia las 24 horas.",
    "tipo_vehiculo": "auto", "largo_m": 5.0, "ancho_m": 2.5, "techada": True,
    "precio_hora": 6.0,
    "direccion": "Av. Larco 345", "distrito": "Miraflores", "referencia": "Frente al parque Kennedy",
    "latitud": -12.1211, "longitud": -77.0297,
    "tarifas": [{"hora_inicio": "18:00", "hora_fin": "22:00", "precio_hora": 9.0}],
    # lunes a viernes de 08:00 a 22:00
    "disponibilidad": [{"dia_semana": d, "hora_inicio": "08:00", "hora_fin": "22:00"} for d in range(5)],
}


def publicar(cliente, cabeceras, fotos=3, **cambios):
    import json
    datos = {**DATOS_COCHERA, **cambios}
    archivos = [("fotos", (f"foto{i}.png", PNG, "image/png")) for i in range(fotos)]
    return cliente.post("/api/cocheras", data={"datos": json.dumps(datos)}, files=archivos, headers=cabeceras)


@pytest.fixture
def escenario(cliente):
    """Un arrendador con una cochera publicada y un arrendatario."""
    cab_dueno, dueno = registrar(cliente, "arrendador", "Rosa Dueña")
    cab_cliente, conductor = registrar(cliente, "arrendatario", "Luis Conductor")
    r = publicar(cliente, cab_dueno)
    assert r.status_code == 201, r.text
    return {"cab_dueno": cab_dueno, "dueno": dueno, "cab_cliente": cab_cliente,
            "conductor": conductor, "cochera": r.json()}
