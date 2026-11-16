"""Tarjetas simuladas del usuario (US-26). El CVV nunca se guarda."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auditoria, pasarela, schemas
from ..database import get_db
from ..deps import usuario_actual
from ..models import MetodoPago, Usuario
from ..security import cifrar

router = APIRouter(prefix="/api/tarjetas", tags=["Tarjetas"])


def _salida(m: MetodoPago) -> schemas.TarjetaSalida:
    return schemas.TarjetaSalida(id=m.id, titular=m.titular, marca=m.marca, ultimos4=m.ultimos4,
                                 vence_mes=m.vence_mes, vence_anio=m.vence_anio)


@router.get("", response_model=List[schemas.TarjetaSalida])
def listar(usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    tarjetas = db.scalars(select(MetodoPago).where(MetodoPago.usuario_id == usuario.id)
                          .order_by(MetodoPago.creado_en)).all()
    return [_salida(t) for t in tarjetas]


@router.post("", response_model=schemas.TarjetaSalida, status_code=status.HTTP_201_CREATED)
def registrar(datos: schemas.TarjetaEntrada, usuario: Usuario = Depends(usuario_actual),
              db: Session = Depends(get_db)):
    numero = pasarela.solo_digitos(datos.numero)
    error = pasarela.validar_tarjeta(numero, datos.vence_mes, datos.vence_anio, datos.cvv)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, error)
    # El CVV se valida arriba y se descarta: no pasa a la base de datos.
    tarjeta = MetodoPago(
        usuario_id=usuario.id, titular=datos.titular.strip().upper(),
        marca=pasarela.marca_de(numero), ultimos4=numero[-4:],
        vence_mes=datos.vence_mes, vence_anio=datos.vence_anio,
        numero_cifrado=cifrar(numero),
    )
    db.add(tarjeta)
    db.flush()
    auditoria.registrar(db, usuario.id, "tarjeta_registrada", "metodo_pago", tarjeta.id,
                        marca=tarjeta.marca, ultimos4=tarjeta.ultimos4)
    db.commit()
    return _salida(tarjeta)


@router.delete("/{tarjeta_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(tarjeta_id: int, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)):
    tarjeta = db.get(MetodoPago, tarjeta_id)
    if tarjeta is None or tarjeta.usuario_id != usuario.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontramos esa tarjeta.")
    db.delete(tarjeta)
    auditoria.registrar(db, usuario.id, "tarjeta_eliminada", "metodo_pago", tarjeta_id)
    db.commit()
