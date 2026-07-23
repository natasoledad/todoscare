"""CRM / gestión financiera multi-clínica (Spec CRM Clínicas).

No es un rol propio: lo consumen el Administrador (consolidado global) y la
Empresa/Clínica (acotada a la suya). El gate RBAC de cada endpoint refleja
la matriz de permisos §7:

    Ver consolidado global   Admin sí · Empresa no · Médico no
    Ver KPIs de su clínica   Admin sí · Empresa sí · Médico no
    Conciliar / marcar pagado Admin sí · Empresa según config (no por defecto)
    Exportar a ERP           Admin sí · Empresa no

El aislamiento por clinic_id lo garantiza el `scope` derivado del ctx en el
servicio, no un clinic_id que venga del request.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.crm import (
    AsientoExportOut,
    ConciliarOut,
    ConsolidadoOut,
    DetalleClinicaOut,
    LiquidacionOut,
)
from app.routers.empresa import empresa_clinic_id
from app.services import crm
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/consolidado", response_model=ConsolidadoOut)
async def consolidado(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CONSOLIDADO_GLOBAL, Action.VER)),
) -> ConsolidadoOut:
    return ConsolidadoOut(**await crm.consolidado(db, ctx, period))


@router.get("/mi-clinica", response_model=DetalleClinicaOut)
async def mi_clinica(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_KPIS_CLINICA, Action.VER)),
) -> DetalleClinicaOut:
    """Atajo para la Empresa/Clínica: los KPIs de su propia clínica sin tener
    que conocer su clinic_id."""
    clinic_id = empresa_clinic_id(ctx)
    return DetalleClinicaOut(**await crm.detalle_clinica(db, ctx, clinic_id, period))


@router.get("/clinicas/{clinic_id}", response_model=DetalleClinicaOut)
async def detalle_clinica(
    clinic_id: uuid.UUID,
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_KPIS_CLINICA, Action.VER)),
) -> DetalleClinicaOut:
    return DetalleClinicaOut(**await crm.detalle_clinica(db, ctx, clinic_id, period))


@router.get("/liquidaciones", response_model=list[LiquidacionOut])
async def liquidaciones(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CONCILIAR, Action.VER)),
) -> list[LiquidacionOut]:
    return [LiquidacionOut(**r) for r in await crm.liquidaciones(db, ctx, period)]


@router.post("/liquidaciones/{split_id}/conciliar", response_model=ConciliarOut)
async def conciliar(
    split_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CONCILIAR, Action.EDITAR)),
) -> ConciliarOut:
    return ConciliarOut(**await crm.conciliar(db, ctx, split_id))


@router.get("/exportar", response_model=list[AsientoExportOut])
async def exportar(
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_EXPORTAR_ERP, Action.VER)),
) -> list[AsientoExportOut]:
    return [AsientoExportOut(**r) for r in await crm.exportar_asientos(db, ctx, period)]
