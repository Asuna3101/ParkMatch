"""Pasarela de pago SIMULADA (requisito 58).

Reproduce el flujo de una pasarela real —validar la tarjeta, cobrar,
reembolsar— sin conectarse a ningún banco ni mover dinero.

Tarjetas de prueba (cualquier fecha futura y cualquier CVV):
    4242 4242 4242 4242   Visa        pago aprobado
    5555 5555 5555 4444   Mastercard  pago aprobado
    4000 0000 0000 9995   Visa        rechazada: fondos insuficientes
    4000 0000 0000 0002   Visa        rechazada por el banco emisor
"""
import secrets
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from . import config
from .security import descifrar


@dataclass
class Resultado:
    ok: bool
    referencia: Optional[str] = None
    motivo: Optional[str] = None


def solo_digitos(numero: str) -> str:
    return "".join(c for c in numero if c.isdigit())


def luhn_valido(numero: str) -> bool:
    """Algoritmo de Luhn: detecta números de tarjeta mal escritos."""
    digitos = [int(c) for c in numero]
    if not 13 <= len(digitos) <= 19:
        return False
    suma = 0
    for i, d in enumerate(reversed(digitos)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        suma += d
    return suma % 10 == 0


def marca_de(numero: str) -> str:
    if numero.startswith("4"):
        return "Visa"
    if numero[:2] in ("51", "52", "53", "54", "55") or 2221 <= int(numero[:4] or 0) <= 2720:
        return "Mastercard"
    if numero[:2] in ("34", "37"):
        return "American Express"
    if numero[:2] in ("36", "38"):
        return "Diners Club"
    return "Tarjeta"


def vencida(mes: int, anio: int, ahora: Optional[datetime] = None) -> bool:
    ahora = ahora or datetime.now(config.ZONA)
    return (anio, mes) < (ahora.year, ahora.month)


def validar_tarjeta(numero: str, mes: int, anio: int, cvv: str) -> Optional[str]:
    """Devuelve el motivo si la tarjeta no es válida; None si lo es."""
    if not luhn_valido(numero):
        return "El número de tarjeta no es válido. Revisa que esté completo."
    if vencida(mes, anio):
        return "La tarjeta está vencida."
    if not (cvv.isdigit() and len(cvv) in (3, 4)):
        return "El código de seguridad debe tener 3 o 4 dígitos."
    return None


def cobrar(metodo, monto: Decimal) -> Resultado:
    """Intenta el cobro. No toca la base de datos: solo responde aprobado o rechazado."""
    numero = descifrar(metodo.numero_cifrado)
    if numero is None:
        return Resultado(False, motivo="No se pudo leer la tarjeta. Regístrala de nuevo.")
    if vencida(metodo.vence_mes, metodo.vence_anio):
        return Resultado(False, motivo="La tarjeta está vencida.")
    if numero.endswith("9995"):
        return Resultado(False, motivo="Fondos insuficientes.")
    if numero.endswith("0002"):
        return Resultado(False, motivo="El banco emisor rechazó la operación.")
    if Decimal(monto) <= 0:
        return Resultado(False, motivo="El monto a cobrar no es válido.")
    return Resultado(True, referencia=f"SBX-{secrets.token_hex(6).upper()}")


def reembolsar(referencia: Optional[str], monto: Decimal) -> Resultado:
    """La devolución en la pasarela simulada siempre se aprueba."""
    return Resultado(True, referencia=f"SBX-R-{secrets.token_hex(5).upper()}")
