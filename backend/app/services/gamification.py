"""Point/level rules. Thresholds are a placeholder — Spec Paciente §10
flags "¿Qué campos exactos exige cada nivel de gamificación?" as an open
question; these numbers just need to be *somewhere* coherent until product
defines the real ones.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.wallet import WalletAccount, WalletTransaction

REGISTER_BONUS_POINTS = 100
ONBOARDING_BONUS_POINTS = 200
DEPENDENT_BONUS_POINTS = 25
FICHA_COMPLETA_BONUS_POINTS = 300

# Spec Paciente §10 flags cashback expiry/caps as undefined — no expiry, no
# per-transaction cap implemented. This rate is a placeholder too.
POINTS_TO_CASHBACK_RATE = 10  # 10 puntos = 1 unidad de cashback

LEVEL_THRESHOLDS = (
    ("Diamante", 3000),
    ("Oro", 1500),
    ("Plata", 300),
    ("Bronce", 0),
)

FICHA_COMPLETE_FIELDS = (
    "fecha_nacimiento",
    "sexo",
    "grupo_sanguineo",
    "alergias",
    "contacto_emergencia",
    "seguro",
)


def level_for_points(points: int) -> str:
    for name, floor in LEVEL_THRESHOLDS:
        if points >= floor:
            return name
    return "Bronce"


def is_ficha_completa(ficha: dict | None) -> bool:
    if not ficha:
        return False
    return all(ficha.get(f) not in (None, "") for f in FICHA_COMPLETE_FIELDS)


async def award(
    db: AsyncSession,
    *,
    wallet: WalletAccount,
    patient: Patient,
    tipo: str,
    puntos: int | None = None,
    cashback: float | None = None,
    motivo: str | None = None,
    ref_id=None,
) -> None:
    """Appends a WalletTransaction, bumps the WalletAccount running balance,
    and recomputes the Patient's cached `nivel`. Caller commits."""
    db.add(
        WalletTransaction(
            clinic_id=wallet.clinic_id,
            wallet_id=wallet.id,
            tipo=tipo,
            puntos=puntos,
            cashback=cashback,
            motivo=motivo,
            ref_id=ref_id,
        )
    )
    if puntos:
        wallet.puntos += puntos
    if cashback:
        wallet.cashback = float(wallet.cashback) + cashback
    patient.nivel = level_for_points(wallet.puntos)
