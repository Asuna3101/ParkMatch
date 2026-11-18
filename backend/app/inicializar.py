"""Prepara la base de datos la primera vez que se ejecuta el backend.

Si la base indicada en DATABASE_URL no existe, la crea. Si todavía no tiene
tablas, aplica db/schema.sql. Si ya tiene datos, no toca nada.
"""
import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

from . import config

SCHEMA = config.RAIZ / "db" / "schema.sql"


def _crear_base_si_falta(url) -> bool:
    """Crea la base con el usuario de la URL, conectándose a la base 'postgres'."""
    nombre = url.database
    conn = psycopg2.connect(
        host=url.host or "localhost", port=url.port or 5432,
        user=url.username, password=url.password, dbname="postgres")
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,))
            if cur.fetchone() is not None:
                return False
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
            return True
    finally:
        conn.close()


def _aplicar_esquema(engine) -> None:
    script = SCHEMA.read_text(encoding="utf-8")
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            cur.execute(script)
        raw.commit()
    finally:
        raw.close()


def asegurar_base_de_datos() -> None:
    url = make_url(config.DATABASE_URL)
    creada = _crear_base_si_falta(url)
    if creada:
        print(f"Base de datos '{url.database}' creada.")
    engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
    try:
        if creada or "usuario" not in inspect(engine).get_table_names():
            _aplicar_esquema(engine)
            print("Tablas creadas desde db/schema.sql.")
    finally:
        engine.dispose()
