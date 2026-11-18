"""Carga datos de demostración.

    python seed.py

BORRA todo lo que haya en las tablas y deja cuatro cuentas, siete cocheras
en Lima, una solicitud pendiente y una conversación. Las "fotografías" son
fotos de demostración incluidas en la carpeta demo_fotos/.

Cuentas (todas con la contraseña  Parkmatch1):
    rosa@parkmatch.pe     arrendadora
    carlos@parkmatch.pe   arrendador
    luis@parkmatch.pe     arrendatario
    maria@parkmatch.pe    arrendataria
    admin@parkmatch.pe    administradora (moderación, disputas y verificaciones)
"""
import uuid
from datetime import datetime, time, timedelta

from sqlalchemy import text

from app import config
from app.database import SessionLocal
from app.inicializar import asegurar_base_de_datos
from app.models import (Calificacion, Cochera, Conversacion, Disponibilidad, FotoCochera, Mensaje,
                        Pago, Reporte, Reserva, Tarifa, Ubicacion, Usuario)
from app.security import hash_contrasena
from app.tarifas import calcular_costo

CLAVE = "Parkmatch1"
PALETAS = [("#DCE9F7", "#2F6FB5"), ("#E3F1E6", "#3B8A5A"), ("#F7EBDD", "#B5732F"),
           ("#ECE6F5", "#6C4FA3"), ("#F6E1E1", "#B04A4A"), ("#E0F0F1", "#2F8791")]
VISTAS = ["Vista del ingreso", "Interior del espacio", "Vista desde la calle"]


DEMO_FOTOS = ["cochera1.jpg", "cochera2.jpg", "cochera3.jpg"]


def ilustracion(titulo: str, vista: str, paleta: int, techada: bool) -> str:
    """Devuelve la URL de una foto de demostración (carpeta demo_fotos/)."""
    return f"/demo/{DEMO_FOTOS[paleta % len(DEMO_FOTOS)]}"


def franjas(dias, inicio, fin):
    return [Disponibilidad(dia_semana=d, hora_inicio=time(*inicio), hora_fin=time(*fin)) for d in dias]


SEMANA = range(0, 5)
TODOS = range(0, 7)

COCHERAS = [
    # (dueño, título, descripción, tipo, largo, ancho, techada, precio, dirección, distrito, referencia, lat, lng, tarifas, calendario)
    ("rosa", "Cochera techada frente al parque Kennedy",
     "Espacio techado con portón eléctrico y cámara de seguridad. Ideal para dejar el auto mientras "
     "trabajas o haces compras en el centro de Miraflores. Ingreso amplio, sin columnas.",
     "auto", 5.2, 2.6, True, 6, "Av. José Larco 345", "Miraflores", "A media cuadra del parque Kennedy",
     -12.121100, -77.029700, [((18, 0), (22, 0), 9)], franjas(SEMANA, (7, 0), (22, 0)) + franjas([5], (9, 0), (20, 0))),
    ("rosa", "Espacio para moto en calle Schell",
     "Espacio cubierto para motos dentro de un edificio residencial con vigilante. Se puede dejar "
     "el casco en el casillero del conserje.",
     "moto", 2.2, 1.2, True, 3, "Calle Schell 280", "Miraflores", "Edificio de ladrillo, timbre 101",
     -12.120500, -77.028300, [], franjas(TODOS, (8, 0), (21, 0))),
    ("rosa", "Cochera en el centro financiero de San Isidro",
     "Cochera en sótano de edificio de oficinas, a dos cuadras de la Vía Expresa. Acceso con "
     "vigilante las 24 horas. Entra un sedán o una SUV mediana.",
     "auto", 5.0, 2.5, True, 8, "Av. Rivera Navarrete 501", "San Isidro", "Sótano 1, espacio 14",
     -12.093100, -77.026000, [((8, 0), (18, 0), 10)], franjas(SEMANA, (6, 0), (23, 0))),
    ("carlos", "Cochera amplia para camioneta en Surco",
     "Cochera descubierta al frente de la casa, con reja y luz por las noches. Entra sin problema "
     "una camioneta doble cabina. Zona tranquila y residencial.",
     "camioneta", 6.0, 3.0, False, 7, "Av. Primavera 1050", "Santiago de Surco", "Casa de reja verde",
     -12.110600, -76.981200, [], franjas(TODOS, (7, 0), (22, 0))),
    ("carlos", "Cochera a una cuadra de la Universidad de Lima",
     "Perfecta para estudiantes y docentes: a una cuadra del ingreso principal de la universidad. "
     "Techada, con portón manual y espacio para maniobrar.",
     "auto", 5.0, 2.5, True, 5, "Av. Javier Prado Este 4600", "Santiago de Surco", "Frente a la puerta 1",
     -12.084700, -76.971700, [((7, 0), (13, 0), 6)], franjas(SEMANA, (7, 0), (22, 0)) + franjas([5], (8, 0), (14, 0))),
    ("carlos", "Cochera en La Molina cerca de La Fontana",
     "Cochera dentro de condominio con control de ingreso. El vigilante anota la placa al entrar. "
     "Disponible todos los días, incluso domingos y feriados.",
     "auto", 5.0, 2.4, False, 4, "Av. La Fontana 750", "La Molina", "Condominio Los Sauces",
     -12.076300, -76.955000, [], franjas(TODOS, (6, 0), (23, 0))),
    ("carlos", "Cochera en San Borja junto al Pentagonito",
     "Espacio techado en casa particular, a pasos del circuito del Pentagonito. Buena opción si "
     "vienes a correr o a una cita médica en la zona.",
     "auto", 4.8, 2.4, True, 5.5, "Av. San Luis 2100", "San Borja", "Casa blanca de dos pisos",
     -12.099000, -76.996000, [], franjas(SEMANA, (8, 0), (20, 0))),
]


def proximo_dia_habil() -> datetime:
    dia = datetime.now(config.ZONA).date() + timedelta(days=1)
    while dia.weekday() > 4:
        dia += timedelta(days=1)
    return datetime.combine(dia, time(0, 0), tzinfo=config.ZONA)


def main() -> None:
    asegurar_base_de_datos()
    with SessionLocal() as db:
        db.execute(text(
            "TRUNCATE log_auditoria, mensaje, conversacion, pago, reserva, disponibilidad, "
            "tarifa, foto_cochera, ubicacion, cochera, usuario RESTART IDENTITY CASCADE"))

        clave = hash_contrasena(CLAVE)
        personas = {
            "rosa": Usuario(nombre="Rosa Quispe", correo="rosa@parkmatch.pe", telefono="987 654 321",
                            rol="arrendador", contrasena_hash=clave),
            "carlos": Usuario(nombre="Carlos Mendoza", correo="carlos@parkmatch.pe", telefono="912 345 678",
                              rol="arrendador", contrasena_hash=clave),
            "luis": Usuario(nombre="Luis Paredes", correo="luis@parkmatch.pe", telefono="998 877 665",
                            rol="arrendatario", contrasena_hash=clave),
            "maria": Usuario(nombre="María Salas", correo="maria@parkmatch.pe", telefono="955 443 322",
                             rol="arrendatario", contrasena_hash=clave),
            "admin": Usuario(nombre="Andrea Admin", correo="admin@parkmatch.pe",
                             rol="administrador", contrasena_hash=clave, verificacion="verificado"),
        }
        personas["rosa"].verificacion = "verificado"
        db.add_all(personas.values())
        db.flush()

        cocheras = []
        for i, (dueno, titulo, descripcion, tipo, largo, ancho, techada, precio, direccion, distrito,
                referencia, lat, lng, tarifas, calendario) in enumerate(COCHERAS):
            c = Cochera(arrendador_id=personas[dueno].id, titulo=titulo, descripcion=descripcion,
                        tipo_vehiculo=tipo, largo_m=largo, ancho_m=ancho, techada=techada, precio_hora=precio)
            c.ubicacion = Ubicacion(direccion=direccion, distrito=distrito, referencia=referencia,
                                    latitud=lat, longitud=lng)
            c.tarifas = [Tarifa(hora_inicio=time(*a), hora_fin=time(*b), precio_hora=p) for a, b, p in tarifas]
            c.disponibilidades = calendario
            c.fotos = [FotoCochera(url=ilustracion(distrito, vista, i + n, techada), orden=n)
                       for n, vista in enumerate(VISTAS)]
            cocheras.append(c)
        db.add_all(cocheras)
        db.flush()

        # Una solicitud pendiente y una conversación, para que la demo no arranque vacía.
        dia = proximo_dia_habil()
        inicio, fin = dia.replace(hour=10), dia.replace(hour=13)
        primera = cocheras[0]
        db.add(Reserva(cochera_id=primera.id, arrendatario_id=personas["luis"].id, inicio=inicio, fin=fin,
                       costo_total=calcular_costo(inicio, fin, primera.precio_hora, primera.tarifas)))
        charla = Conversacion(cochera_id=primera.id, arrendatario_id=personas["luis"].id,
                              arrendador_id=personas["rosa"].id)
        db.add(charla)
        db.flush()
        db.add_all([
            Mensaje(conversacion_id=charla.id, emisor_id=personas["luis"].id,
                    texto="Hola, Rosa. ¿La cochera tiene altura suficiente para una SUV?"),
            Mensaje(conversacion_id=charla.id, emisor_id=personas["rosa"].id,
                    texto="Hola, Luis. Sí, entra sin problema: el portón tiene 2.10 m de alto."),
            Mensaje(conversacion_id=charla.id, emisor_id=personas["luis"].id,
                    texto="Perfecto. Te acabo de enviar una solicitud para mañana."),
        ])

        # Historial: reservas ya terminadas, con su pago y sus calificaciones (US-20 a US-22).
        resenas = [
            (0, "maria", 5, 4, "Muy fácil de ubicar y el portón eléctrico funciona perfecto.",
             "Puntual y cuidadosa al estacionar."),
            (0, "luis", 4, 5, "Buena cochera, aunque el ingreso es un poco estrecho.", "Todo en orden, recomendado."),
            (2, "maria", 5, None, "Seguro y con vigilante. Volveré a reservar.", None),
            (3, "luis", 3, 4, "Cumple, pero la iluminación de noche es poca.", "Dejó el espacio limpio."),
        ]
        hoy = datetime.now(config.ZONA).replace(minute=0, second=0, microsecond=0)
        for n, (indice, quien, estrellas_cochera, estrellas_conductor, texto, texto_dueno) in enumerate(resenas):
            c = cocheras[indice]
            ini = (hoy - timedelta(days=3 + n * 4)).replace(hour=9)
            fn = ini.replace(hour=11)
            costo = calcular_costo(ini, fn, c.precio_hora, c.tarifas)
            r = Reserva(cochera_id=c.id, arrendatario_id=personas[quien].id, inicio=ini, fin=fn,
                        estado="finalizada", costo_total=costo, ingreso_real=ini, salida_real=fn)
            db.add(r)
            db.flush()
            db.add(Pago(reserva_id=r.id, monto=costo, estado="pagado", medio="efectivo", pagado_en=ini))
            db.add(Calificacion(reserva_id=r.id, autor_id=personas[quien].id, destinatario_id=c.arrendador_id,
                                estrellas=estrellas_cochera, comentario=texto))
            if estrellas_conductor:
                db.add(Calificacion(reserva_id=r.id, autor_id=c.arrendador_id,
                                    destinatario_id=personas[quien].id,
                                    estrellas=estrellas_conductor, comentario=texto_dueno))

        # Un reporte pendiente, para que el panel de moderación tenga algo que revisar.
        db.add(Reporte(cochera_id=cocheras[-1].id, autor_id=personas["maria"].id, motivo="fotos_enganosas",
                       detalle="Las fotos no coinciden con el lugar: el espacio es más pequeño."))
        db.commit()

    print("Datos de demostración cargados.")
    print(f"  5 cuentas (contraseña: {CLAVE}), {len(COCHERAS)} cocheras, 1 solicitud y 1 conversación.")
    print("  Arrendadores:  rosa@parkmatch.pe · carlos@parkmatch.pe")
    print("  Arrendatarios: luis@parkmatch.pe · maria@parkmatch.pe")
    print("  Administradora: admin@parkmatch.pe")


if __name__ == "__main__":
    main()
