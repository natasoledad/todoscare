"""Cascada de copago chileno.

En Chile el precio de una prestación no lo paga entero el paciente: primero la
previsión (Fonasa/Isapre) bonifica vía bono electrónico (I-Med), y sobre el
copago resultante pueden actuar todavía dos capas más antes de que el paciente
pague de su bolsillo:

    precio → bono previsión → seguro complementario → caja de compensación (CCAF) → copago final

Este servicio arma esa cascada de forma determinista y reutilizable (la usan la
calculadora del catálogo y la caja al cobrar). Todo en pesos enteros (CLP no
tiene decimales)."""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copago import CoberturaComplementaria
from app.tenancy.context import TenantContext

# Orden de aplicación de las capas: el seguro complementario reembolsa sobre el
# copago de la previsión; la caja de compensación bonifica el residuo.
_ORDEN = {"seguro_complementario": 0, "caja_compensacion": 1}


def _clp(x) -> int:
    """Redondea a peso entero (medio hacia arriba)."""
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calcular_cascada(precio: float, *, prevision_pct: float = 0.0, prevision_bono: float | None = None, capas: list[dict]) -> dict:
    """Calcula el desglose del copago.

    `precio`         valor total de la prestación (CLP).
    `prevision_pct`  fracción 0..1 que bonifica Fonasa/Isapre (si no se pasa un
                     bono fijo). `prevision_bono` tiene prioridad si viene.
    `capas`          coberturas complementarias, cada una:
                     {tipo, nombre, modalidad(porcentaje|monto), valor,
                      tope?, deducible?, permite_cuotas?}

    Devuelve precio, bono de previsión, copago tras previsión, la lista de
    aportes (incluida la previsión como primera línea) y el copago final."""
    precio = max(0.0, float(precio))
    # ── Previsión (Fonasa/Isapre) ──
    if prevision_bono is not None:
        bono_prev = min(_clp(prevision_bono), _clp(precio))
    else:
        pct = min(max(float(prevision_pct), 0.0), 1.0)
        bono_prev = min(_clp(precio * pct), _clp(precio))
    copago = _clp(precio) - bono_prev
    copago_inicial = copago

    aportes: list[dict] = [{"tipo": "prevision", "nombre": "Bono previsión (Fonasa/Isapre)", "aporte": bono_prev}]
    permite_cuotas = False

    # ── Capas complementarias, en orden (seguro → caja) ──
    for capa in sorted(capas, key=lambda c: _ORDEN.get(c.get("tipo", ""), 9)):
        if copago <= 0:
            aportes.append({"tipo": capa.get("tipo"), "nombre": capa.get("nombre"), "aporte": 0})
            continue
        deducible = _clp(capa.get("deducible") or 0)
        imponible = max(0, copago - deducible)
        modalidad = capa.get("modalidad", "porcentaje")
        if modalidad == "monto":
            aporte = _clp(capa.get("valor") or 0)
        else:  # porcentaje
            valor = min(max(float(capa.get("valor") or 0), 0.0), 1.0)
            aporte = _clp(imponible * valor)
        tope = capa.get("tope")
        if tope is not None:
            aporte = min(aporte, _clp(tope))
        aporte = max(0, min(aporte, copago))  # nunca aporta más que el copago vigente
        copago -= aporte
        if capa.get("permite_cuotas"):
            permite_cuotas = True
        aportes.append({"tipo": capa.get("tipo"), "nombre": capa.get("nombre"), "aporte": aporte})

    return {
        "precio": _clp(precio),
        "bono_prevision": bono_prev,
        "prevision_pct": (None if prevision_bono is not None else min(max(float(prevision_pct), 0.0), 1.0)),
        "copago_inicial": copago_inicial,
        "aportes": aportes,
        "copago_final": copago,
        "permite_cuotas": permite_cuotas,
    }


# ─────────────────────────── catálogo (CRUD) ───────────────────────────
async def listar(db: AsyncSession, clinic_id: uuid.UUID, *, solo_activas: bool = False) -> list[CoberturaComplementaria]:
    q = select(CoberturaComplementaria).where(
        CoberturaComplementaria.clinic_id == clinic_id,
        CoberturaComplementaria.deleted_at.is_(None),
    )
    if solo_activas:
        q = q.where(CoberturaComplementaria.activo.is_(True))
    return list((await db.execute(q.order_by(CoberturaComplementaria.tipo, CoberturaComplementaria.nombre))).scalars().all())


async def obtener(db: AsyncSession, clinic_id: uuid.UUID, cobertura_id: uuid.UUID) -> CoberturaComplementaria | None:
    c = await db.get(CoberturaComplementaria, cobertura_id)
    if c is None or c.deleted_at is not None or c.clinic_id != clinic_id:
        return None
    return c


async def cargar_capas(db: AsyncSession, clinic_id: uuid.UUID, ids: list[uuid.UUID]) -> list[dict]:
    """Trae las coberturas por id (validando tenant + activas) y las convierte
    al formato que consume `calcular_cascada`."""
    if not ids:
        return []
    rows = (
        await db.execute(
            select(CoberturaComplementaria).where(
                CoberturaComplementaria.clinic_id == clinic_id,
                CoberturaComplementaria.id.in_(ids),
                CoberturaComplementaria.activo.is_(True),
                CoberturaComplementaria.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    por_id = {c.id: c for c in rows}
    capas = []
    for cid in ids:  # respeta el orden pedido
        c = por_id.get(cid)
        if c is None:
            continue
        capas.append({
            "tipo": c.tipo, "nombre": c.nombre, "modalidad": c.modalidad,
            "valor": float(c.valor), "tope": (float(c.tope) if c.tope is not None else None),
            "deducible": (float(c.deducible) if c.deducible is not None else None),
            "permite_cuotas": c.permite_cuotas,
        })
    return capas
