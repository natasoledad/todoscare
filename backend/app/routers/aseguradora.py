"""Rol Aseguradora / Prestador (Spec Aseguradora Prestador §3 RBAC).

    Convenios y aranceles      V C E(versión) D(baja)
    Padrón de afiliados        V Alta E Baja
    Autorizaciones             V — Resolver —
    Liquidaciones              V — Conciliar/pagar —
    Ficha clínica del afiliado Solo lo autorizado y auditado

El alcance es la entidad aseguradora del usuario (ctx.insurer_ids()), no un
tenant clínico; el servicio verifica que cada convenio/afiliado/autorización
pertenezca a esa aseguradora antes de tocarlo.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.schemas.aseguradora import (
    AfiliadoOut,
    AltaAfiliadoIn,
    ArancelOut,
    AseguradoraKpis,
    AutorizacionOut,
    ConvenioOut,
    CrearArancelIn,
    FichaAfiliadoOut,
    GenerarLiquidacionIn,
    LiquidacionOut,
    LiquidacionResultOut,
    PagoOut,
    RedOut,
    ResolverIn,
    ResolverOut,
)
from app.services import aseguradora as svc
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/aseguradora", tags=["aseguradora"])


# ─────────── inicio / KPIs ───────────
@router.get("/inicio", response_model=AseguradoraKpis)
async def inicio(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.AUTORIZACIONES, Action.VER))) -> AseguradoraKpis:
    return AseguradoraKpis(**await svc.inicio(db, ctx))


# ─────────── convenios y aranceles ───────────
@router.get("/convenios", response_model=list[ConvenioOut])
async def convenios(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.CONVENIOS_ARANCELES, Action.VER))) -> list[ConvenioOut]:
    return [ConvenioOut(**c) for c in await svc.convenios(db, ctx)]


@router.get("/convenios/{agreement_id}/aranceles", response_model=list[ArancelOut])
async def aranceles(agreement_id: uuid.UUID, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.CONVENIOS_ARANCELES, Action.VER))) -> list[ArancelOut]:
    return [ArancelOut(**a) for a in await svc.aranceles(db, ctx, agreement_id)]


@router.post("/convenios/{agreement_id}/aranceles", response_model=ArancelOut, status_code=201)
async def crear_arancel(agreement_id: uuid.UUID, body: CrearArancelIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.CONVENIOS_ARANCELES, Action.CREAR))) -> ArancelOut:
    await svc.crear_arancel(db, ctx, agreement_id, service_id=body.service_id, cobertura_pct=body.cobertura_pct, copago=body.copago)
    # devolver la fila con el nombre del servicio ya resuelto
    fila = next(a for a in await svc.aranceles(db, ctx, agreement_id) if a["service_id"] == body.service_id)
    return ArancelOut(**fila)


# ─────────── padrón de afiliados ───────────
@router.get("/afiliados", response_model=list[AfiliadoOut])
async def afiliados(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.PADRON_AFILIADOS, Action.VER))) -> list[AfiliadoOut]:
    return [AfiliadoOut(**a) for a in await svc.padron(db, ctx)]


@router.post("/afiliados", response_model=AfiliadoOut, status_code=201)
async def alta_afiliado(body: AltaAfiliadoIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.PADRON_AFILIADOS, Action.CREAR))) -> AfiliadoOut:
    await svc.alta_afiliado(db, ctx, documento_identidad=body.documento_identidad, plan_cobertura=body.plan_cobertura, vigencia_desde=body.vigencia_desde, vigencia_hasta=body.vigencia_hasta)
    # devolver la fila completa (con vigencia calculada) tras el alta
    padron = await svc.padron(db, ctx)
    fila = next(a for a in padron if a["documento_identidad"] == body.documento_identidad)
    return AfiliadoOut(**fila)


@router.delete("/afiliados/{affiliate_id}", status_code=204)
async def baja_afiliado(affiliate_id: uuid.UUID, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.PADRON_AFILIADOS, Action.ELIMINAR))) -> None:
    await svc.baja_afiliado(db, ctx, affiliate_id)


# ─────────── autorizaciones ───────────
@router.get("/autorizaciones", response_model=list[AutorizacionOut])
async def autorizaciones(estado: str | None = None, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.AUTORIZACIONES, Action.VER))) -> list[AutorizacionOut]:
    return [AutorizacionOut(**a) for a in await svc.autorizaciones(db, ctx, estado)]


@router.post("/autorizaciones/{authorization_id}/resolver", response_model=ResolverOut)
async def resolver(authorization_id: uuid.UUID, body: ResolverIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.AUTORIZACIONES, Action.EDITAR))) -> ResolverOut:
    return ResolverOut(**await svc.resolver(db, ctx, authorization_id, decision=body.decision, motivo=body.motivo))


# ─────────── liquidaciones ───────────
@router.get("/liquidaciones", response_model=list[LiquidacionOut])
async def liquidaciones(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.LIQUIDACIONES_ASEGURADORA, Action.VER))) -> list[LiquidacionOut]:
    return [LiquidacionOut(**s) for s in await svc.liquidaciones(db, ctx)]


@router.post("/convenios/{agreement_id}/liquidaciones", response_model=LiquidacionResultOut, status_code=201)
async def generar_liquidacion(agreement_id: uuid.UUID, body: GenerarLiquidacionIn, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.LIQUIDACIONES_ASEGURADORA, Action.EDITAR))) -> LiquidacionResultOut:
    return LiquidacionResultOut(**await svc.generar_liquidacion(db, ctx, agreement_id, body.periodo))


@router.post("/liquidaciones/{settlement_id}/pagar", response_model=PagoOut)
async def pagar_liquidacion(settlement_id: uuid.UUID, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.LIQUIDACIONES_ASEGURADORA, Action.EDITAR))) -> PagoOut:
    return PagoOut(**await svc.pagar_liquidacion(db, ctx, settlement_id))


# ─────────── red de prestadores ───────────
@router.get("/red", response_model=list[RedOut])
async def red(db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.CONVENIOS_ARANCELES, Action.VER))) -> list[RedOut]:
    return [RedOut(**r) for r in await svc.red(db, ctx)]


# ─────────── ficha del afiliado (minimizada + auditada) ───────────
@router.get("/afiliados/{patient_id}/ficha", response_model=FichaAfiliadoOut)
async def ficha_afiliado(patient_id: uuid.UUID, db: AsyncSession = Depends(get_db), ctx: TenantContext = Depends(require(Resource.FICHA_AFILIADO_AUTORIZADA, Action.VER))) -> FichaAfiliadoOut:
    return FichaAfiliadoOut(**await svc.ficha_afiliado(db, ctx, patient_id))
