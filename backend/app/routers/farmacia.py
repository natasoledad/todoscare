from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.clinical import MedicalRecord, Prescription
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.patients import get_own_patient
from app.schemas.farmacia import MedicamentoOut
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/farmacia", tags=["farmacia"])


@router.get("/medicamentos", response_model=list[MedicamentoOut])
async def list_medicamentos(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.OWN_MEDICAL_RECORD, Action.VER)),
) -> list[MedicamentoOut]:
    patient = await get_own_patient(db, ctx)
    rows = (
        await db.execute(
            select(Prescription)
            .join(MedicalRecord, MedicalRecord.id == Prescription.record_id)
            .where(MedicalRecord.patient_id == patient.id, Prescription.estado == "vigente", Prescription.deleted_at.is_(None))
            .order_by(Prescription.created_at.desc())
        )
    ).scalars().all()

    out: list[MedicamentoOut] = []
    for prescription in rows:
        for item in prescription.items or []:
            out.append(
                MedicamentoOut(
                    nombre=item.get("medicamento", ""),
                    cantidad=item.get("cantidad", ""),
                    indicaciones=item.get("indicaciones"),
                    precio=item.get("precio"),
                )
            )
    return out
