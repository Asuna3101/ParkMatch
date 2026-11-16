"""Publicación, búsqueda y detalle de cocheras.

Requisitos 6, 8, 9, 10, 12, 16 y 23 · US-05, US-06, US-07, US-09, US-12, US-18.
"""
import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import auditoria, config, schemas
from ..database import get_db
from ..deps import solo_arrendador
from ..disponibilidad import evaluar
from ..models import Cochera, Disponibilidad, FotoCochera, Reserva, Tarifa, Ubicacion, Usuario

router = APIRouter(prefix="/api/cocheras", tags=["Cocheras"])


# ----------------------------------------------------------------- utilidades
def _resumen(c: Cochera, distancia: Optional[float] = None) -> schemas.CocheraResumen:
    return schemas.CocheraResumen(
        id=c.id, titulo=c.titulo, tipo_vehiculo=c.tipo_vehiculo, techada=c.techada,
        precio_hora=float(c.precio_hora), activa=c.activa,
        direccion=c.ubicacion.direccion, distrito=c.ubicacion.distrito,
        latitud=float(c.ubicacion.latitud), longitud=float(c.ubicacion.longitud),
        foto=c.fotos[0].url if c.fotos else None,
        distancia_km=round(distancia, 2) if distancia is not None else None,
    )


def _cochera_o_404(db: Session, cochera_id: int) -> Cochera:
    cochera = db.get(Cochera, cochera_id)
    if cochera is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa cochera.")
    return cochera


def _propia_o_403(db: Session, cochera_id: int, usuario: Usuario) -> Cochera:
    cochera = _cochera_o_404(db, cochera_id)
    if cochera.arrendador_id != usuario.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo puedes modificar tus propias cocheras.")
    return cochera


def _guardar_foto(foto: UploadFile) -> str:
    extension = config.TIPOS_FOTO.get(foto.content_type or "")
    if extension is None:
        raise HTTPException(
            422,
            f"«{foto.filename}» no es una imagen válida. Usa JPG, PNG o WebP.",
        )
    contenido = foto.file.read()
    if len(contenido) > config.MAX_BYTES_FOTO:
        raise HTTPException(
            422,
            f"«{foto.filename}» pesa más de 5 MB.",
        )
    nombre = f"{uuid.uuid4().hex}{extension}"
    (config.CARPETA_UPLOADS / nombre).write_bytes(contenido)
    return f"/uploads/{nombre}"


# ------------------------------------------------------------------ publicar
@router.post("", response_model=schemas.CocheraDetalle, status_code=status.HTTP_201_CREATED)
def publicar(
    datos: str = Form(..., description="JSON con los datos del anuncio"),
    fotos: List[UploadFile] = File(...),
    usuario: Usuario = Depends(solo_arrendador),
    db: Session = Depends(get_db),
):
    """Crea el anuncio completo: datos, ubicación, fotos, tarifas y calendario."""
    try:
        entrada = schemas.CocheraEntrada.model_validate(json.loads(datos))
    except json.JSONDecodeError:
        raise HTTPException(422, "Los datos del anuncio no son válidos.")
    except ValidationError as error:
        mensaje = error.errors()[0]["msg"].replace("Value error, ", "")
        campo = ".".join(str(p) for p in error.errors()[0]["loc"])
        raise HTTPException(422, f"{campo}: {mensaje}" if campo else mensaje)

    if len(fotos) < config.MIN_FOTOS:
        raise HTTPException(
            422,
            f"Sube al menos {config.MIN_FOTOS} fotografías de la cochera.",
        )
    if len(fotos) > config.MAX_FOTOS:
        raise HTTPException(
            422,
            f"Puedes subir hasta {config.MAX_FOTOS} fotografías.",
        )

    cochera = Cochera(
        arrendador_id=usuario.id, titulo=entrada.titulo.strip(), descripcion=entrada.descripcion.strip(),
        tipo_vehiculo=entrada.tipo_vehiculo, largo_m=entrada.largo_m, ancho_m=entrada.ancho_m,
        techada=entrada.techada, precio_hora=entrada.precio_hora,
    )
    cochera.ubicacion = Ubicacion(
        direccion=entrada.direccion.strip(), distrito=entrada.distrito.strip(),
        referencia=(entrada.referencia or "").strip() or None,
        latitud=entrada.latitud, longitud=entrada.longitud,
    )
    cochera.tarifas = [Tarifa(**t.model_dump()) for t in entrada.tarifas]
    cochera.disponibilidades = [Disponibilidad(**d.model_dump()) for d in entrada.disponibilidad]
    cochera.fotos = [FotoCochera(url=_guardar_foto(f), orden=i) for i, f in enumerate(fotos)]

    db.add(cochera)
    db.flush()
    auditoria.registrar(db, usuario.id, "cochera_publicada", "cochera", cochera.id, titulo=cochera.titulo)
    db.commit()
    return _detalle(db, cochera)


# -------------------------------------------------------------------- listar
@router.get("/mias", response_model=List[schemas.CocheraResumen])
def mis_cocheras(usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    cocheras = db.scalars(
        select(Cochera)
        .where(Cochera.arrendador_id == usuario.id)
        .options(selectinload(Cochera.ubicacion), selectinload(Cochera.fotos))
        .order_by(Cochera.creado_en.desc())
    ).all()
    return [_resumen(c) for c in cocheras]


@router.get("/buscar", response_model=List[schemas.CocheraResumen])
def buscar(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radio_km: float = Query(3, gt=0, le=50),
    db: Session = Depends(get_db),
):
    """Cocheras activas alrededor de un punto, de la más cercana a la más lejana.

    La distancia se calcula con la fórmula del semiverseno directamente en
    PostgreSQL. Antes se descarta con un rectángulo lo que claramente queda
    fuera, para aprovechar el índice de coordenadas (requisito 34).
    """
    distancia = 6371 * func.acos(func.least(1.0,
        func.cos(func.radians(lat)) * func.cos(func.radians(Ubicacion.latitud))
        * func.cos(func.radians(Ubicacion.longitud) - func.radians(lng))
        + func.sin(func.radians(lat)) * func.sin(func.radians(Ubicacion.latitud))
    ))
    margen_lat = radio_km / 111.0
    margen_lng = radio_km / (111.0 * max(0.1, abs(math.cos(math.radians(lat)))))

    filas = db.execute(
        select(Cochera, distancia.label("distancia"))
        .join(Ubicacion, Ubicacion.cochera_id == Cochera.id)
        .where(
            Cochera.activa.is_(True),
            Ubicacion.latitud.between(lat - margen_lat, lat + margen_lat),
            Ubicacion.longitud.between(lng - margen_lng, lng + margen_lng),
            distancia <= radio_km,
        )
        .options(selectinload(Cochera.ubicacion), selectinload(Cochera.fotos))
        .order_by("distancia")
        .limit(100)
    ).all()
    return [_resumen(c, float(d)) for c, d in filas]


# ------------------------------------------------------------------- detalle
def _detalle(db: Session, c: Cochera) -> schemas.CocheraDetalle:
    ahora = datetime.now(timezone.utc)
    ocupado = db.execute(
        select(Reserva.inicio, Reserva.fin)
        .where(Reserva.cochera_id == c.id, Reserva.estado == "confirmada",
               Reserva.fin > ahora, Reserva.inicio < ahora + timedelta(days=30))
        .order_by(Reserva.inicio)
    ).all()
    return schemas.CocheraDetalle(
        id=c.id, titulo=c.titulo, descripcion=c.descripcion, tipo_vehiculo=c.tipo_vehiculo,
        largo_m=float(c.largo_m), ancho_m=float(c.ancho_m), techada=c.techada,
        precio_hora=float(c.precio_hora), activa=c.activa,
        arrendador_id=c.arrendador_id, arrendador_nombre=c.arrendador.nombre,
        ubicacion=schemas.UbicacionSalida.model_validate(c.ubicacion),
        fotos=[f.url for f in c.fotos],
        tarifas=[schemas.FranjaTarifa.model_validate(t) for t in c.tarifas],
        disponibilidad=[schemas.FranjaDisponible.model_validate(d) for d in c.disponibilidades],
        ocupado=[schemas.Ocupado(inicio=i, fin=f) for i, f in ocupado],
    )


@router.get("/{cochera_id}", response_model=schemas.CocheraDetalle)
def detalle(cochera_id: int, db: Session = Depends(get_db)):
    return _detalle(db, _cochera_o_404(db, cochera_id))


@router.get("/{cochera_id}/cotizar", response_model=schemas.Cotizacion)
def cotizar(cochera_id: int, inicio: datetime, fin: datetime, db: Session = Depends(get_db)):
    """Costo de un horario antes de solicitarlo (US-18)."""
    cochera = _cochera_o_404(db, cochera_id)
    motivo, costo, minutos = evaluar(db, cochera, inicio, fin)
    return schemas.Cotizacion(disponible=motivo is None, motivo=motivo,
                              minutos=minutos, costo_total=float(costo))


# -------------------------------------------------------- gestión del anuncio
@router.put("/{cochera_id}", response_model=schemas.CocheraDetalle)
def editar(cochera_id: int, datos: schemas.CocheraEdicion,
           usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """Corrige los datos del anuncio: título, descripción, medidas y ubicación (requisito 7)."""
    cochera = _propia_o_403(db, cochera_id, usuario)
    cochera.titulo = datos.titulo.strip()
    cochera.descripcion = datos.descripcion.strip()
    cochera.tipo_vehiculo = datos.tipo_vehiculo
    cochera.largo_m = datos.largo_m
    cochera.ancho_m = datos.ancho_m
    cochera.techada = datos.techada
    cochera.ubicacion.direccion = datos.direccion.strip()
    cochera.ubicacion.distrito = datos.distrito.strip()
    cochera.ubicacion.referencia = (datos.referencia or "").strip() or None
    cochera.ubicacion.latitud = datos.latitud
    cochera.ubicacion.longitud = datos.longitud
    auditoria.registrar(db, usuario.id, "cochera_editada", "cochera", cochera.id, titulo=cochera.titulo)
    db.commit()
    return _detalle(db, cochera)


@router.patch("/{cochera_id}/estado", response_model=schemas.CocheraResumen)
def cambiar_estado(cochera_id: int, datos: schemas.EstadoEntrada,
                   usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """Activa o pausa el anuncio (requisito 8)."""
    cochera = _propia_o_403(db, cochera_id, usuario)
    cochera.activa = datos.activa
    auditoria.registrar(db, usuario.id, "cochera_activada" if datos.activa else "cochera_pausada",
                        "cochera", cochera.id)
    db.commit()
    return _resumen(cochera)


@router.put("/{cochera_id}/tarifas", response_model=schemas.CocheraDetalle)
def guardar_tarifas(cochera_id: int, datos: schemas.TarifasEntrada,
                    usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """Reemplaza el precio base y las tarifas por franja. Aplica de inmediato (US-06)."""
    cochera = _propia_o_403(db, cochera_id, usuario)
    cochera.precio_hora = datos.precio_hora
    cochera.tarifas = [Tarifa(**t.model_dump()) for t in datos.tarifas]
    auditoria.registrar(db, usuario.id, "tarifas_actualizadas", "cochera", cochera.id,
                        precio_hora=float(datos.precio_hora), franjas=len(datos.tarifas))
    db.commit()
    return _detalle(db, cochera)


@router.put("/{cochera_id}/disponibilidad", response_model=schemas.CocheraDetalle)
def guardar_disponibilidad(cochera_id: int, datos: schemas.DisponibilidadEntrada,
                           usuario: Usuario = Depends(solo_arrendador), db: Session = Depends(get_db)):
    """Reemplaza el calendario semanal (US-07)."""
    cochera = _propia_o_403(db, cochera_id, usuario)
    cochera.disponibilidades = [Disponibilidad(**d.model_dump()) for d in datos.franjas]
    auditoria.registrar(db, usuario.id, "calendario_actualizado", "cochera", cochera.id,
                        franjas=len(datos.franjas))
    db.commit()
    return _detalle(db, cochera)
