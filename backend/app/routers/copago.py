"""Coberturas de copago (Chile): catálogo de seguros complementarios y cajas de
compensación + calculadora de la cascada de copago. La clínica arma su catálogo
y la caja lo usa para llegar al copago final que paga el paciente."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.copago import CoberturaComplementaria
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.copago import (
    CalcularCopagoIn,
    CalcularCopagoOut,
    CoberturaIn,
    CoberturaOut,
    CoberturaUpdate,
)
from app.services import copago as svc
from app.services.medico import audit
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/copago", tags=["copago"])


def _out(c: CoberturaComplementaria) -> CoberturaOut:
    return CoberturaOut(
        id=c.id, tipo=c.tipo, nombre=c.nombre, modalidad=c.modalidad, valor=float(c.valor),
        tope=(float(c.tope) if c.tope is not None else None),
        deducible=(float(c.deducible) if c.deducible is not None else None),
        permite_cuotas=c.permite_cuotas, activo=c.activo,
    )


@router.get("/coberturas", response_model=list[CoberturaOut])
async def listar_coberturas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> list[CoberturaOut]:
    clinic_id = empresa_clinic_id(ctx)
    return [_out(c) for c in await svc.listar(db, clinic_id)]


@router.post("/coberturas", response_model=CoberturaOut, status_code=status.HTTP_201_CREATED)
async def crear_cobertura(
    payload: CoberturaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.CREAR)),
) -> CoberturaOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.modalidad == "porcentaje" and payload.valor > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "En modalidad porcentaje, el valor es una fracción (0 a 1).")
    c = CoberturaComplementaria(
        clinic_id=clinic_id, tipo=payload.tipo, nombre=payload.nombre, modalidad=payload.modalidad,
        valor=payload.valor, tope=payload.tope, deducible=payload.deducible, permite_cuotas=payload.permite_cuotas,
    )
    db.add(c)
    audit(db, ctx, clinic_id=clinic_id, accion="crear_cobertura_copago", recurso=f"cobertura:{payload.nombre}")
    await db.commit()
    await db.refresh(c)
    return _out(c)


@router.patch("/coberturas/{cobertura_id}", response_model=CoberturaOut)
async def editar_cobertura(
    cobertura_id: uuid.UUID,
    payload: CoberturaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.EDITAR)),
) -> CoberturaOut:
    clinic_id = empresa_clinic_id(ctx)
    c = await svc.obtener(db, clinic_id, cobertura_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobertura no encontrada")
    datos = payload.model_dump(exclude_unset=True)
    modalidad = datos.get("modalidad", c.modalidad)
    valor = datos.get("valor", float(c.valor))
    if modalidad == "porcentaje" and valor is not None and valor > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "En modalidad porcentaje, el valor es una fracción (0 a 1).")
    for k, v in datos.items():
        setattr(c, k, v)
    audit(db, ctx, clinic_id=clinic_id, accion="editar_cobertura_copago", recurso=f"cobertura:{c.id}")
    await db.commit()
    await db.refresh(c)
    return _out(c)


@router.delete("/coberturas/{cobertura_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_cobertura(
    cobertura_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.EDITAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    c = await svc.obtener(db, clinic_id, cobertura_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cobertura no encontrada")
    await db.delete(c)  # baja lógica (soft-delete global)
    audit(db, ctx, clinic_id=clinic_id, accion="eliminar_cobertura_copago", recurso=f"cobertura:{c.id}")
    await db.commit()


@router.post("/calcular", response_model=CalcularCopagoOut)
async def calcular_copago(
    payload: CalcularCopagoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CAJAS, Action.VER)),
) -> CalcularCopagoOut:
    """Cascada precio → previsión → seguro complementario → CCAF → copago final."""
    clinic_id = empresa_clinic_id(ctx)
    capas = await svc.cargar_capas(db, clinic_id, payload.cobertura_ids)
    desglose = svc.calcular_cascada(
        payload.precio,
        prevision_pct=payload.prevision_pct,
        prevision_bono=payload.prevision_bono,
        capas=capas,
    )
    return CalcularCopagoOut(**desglose)
