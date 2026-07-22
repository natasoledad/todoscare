from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.wallet import WalletAccount, WalletTransaction
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.patients import get_own_patient
from app.schemas.wallet import CanjearPuntosInput, MovimientoOut, PagarCashbackInput, WalletBalanceOut
from app.services.gamification import POINTS_TO_CASHBACK_RATE, award
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/billetera", tags=["billetera"])


async def _get_wallet(db: AsyncSession, patient_id) -> WalletAccount:
    return (await db.execute(select(WalletAccount).where(WalletAccount.patient_id == patient_id))).scalar_one()


@router.get("", response_model=WalletBalanceOut)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.WALLET, Action.VER)),
) -> WalletBalanceOut:
    patient = await get_own_patient(db, ctx)
    wallet = await _get_wallet(db, patient.id)
    return WalletBalanceOut(puntos=wallet.puntos, cashback=float(wallet.cashback))


@router.get("/movimientos", response_model=list[MovimientoOut])
async def list_movimientos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.WALLET, Action.VER)),
) -> list[MovimientoOut]:
    patient = await get_own_patient(db, ctx)
    wallet = await _get_wallet(db, patient.id)
    rows = (
        await db.execute(select(WalletTransaction).where(WalletTransaction.wallet_id == wallet.id).order_by(WalletTransaction.created_at.desc()))
    ).scalars().all()
    return [MovimientoOut(tipo=t.tipo, fecha=t.created_at, puntos=t.puntos, cashback=float(t.cashback) if t.cashback is not None else None, motivo=t.motivo) for t in rows]


@router.post("/pagar-cashback", response_model=WalletBalanceOut)
async def pagar_cashback(
    payload: PagarCashbackInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.WALLET, Action.EDITAR)),
) -> WalletBalanceOut:
    patient = await get_own_patient(db, ctx)
    wallet = await _get_wallet(db, patient.id)
    if float(wallet.cashback) < payload.monto:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cashback insuficiente")

    await award(db, wallet=wallet, patient=patient, tipo="pago_cashback", cashback=-payload.monto, motivo="Pago con cashback")
    await db.commit()
    return WalletBalanceOut(puntos=wallet.puntos, cashback=float(wallet.cashback))


@router.post("/canjear-puntos", response_model=WalletBalanceOut)
async def canjear_puntos(
    payload: CanjearPuntosInput,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.WALLET, Action.EDITAR)),
) -> WalletBalanceOut:
    patient = await get_own_patient(db, ctx)
    wallet = await _get_wallet(db, patient.id)
    if wallet.puntos < payload.puntos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Puntos insuficientes")

    cashback_ganado = payload.puntos / POINTS_TO_CASHBACK_RATE
    await award(db, wallet=wallet, patient=patient, tipo="canje_puntos", puntos=-payload.puntos, cashback=cashback_ganado, motivo="Canje de puntos por cashback")
    await db.commit()
    return WalletBalanceOut(puntos=wallet.puntos, cashback=float(wallet.cashback))
