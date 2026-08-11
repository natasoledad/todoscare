"""Documentos tributarios electrónicos (Tanda 7).

La clínica (rol Empresa) configura su emisor fiscal y sus folios/CAF, y emite
el documento que corresponde a su país (DTE ante el SII en Chile; Nota Fiscal
municipal/estadual en Brasil). El Administrador supervisa (solo lectura). La
mecánica de emisión vive en el conector `app/integrations/tributario`, que
enruta por país, calcula el impuesto y deja traza — esta capa solo expone la
frontera HTTP y aplica el aislamiento por clínica y el RBAC.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations import tributario as conn
from app.models.tax import TaxDocument, TaxEmitter, TaxFolioRange
from app.models.tenant import Clinic
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.tributario import (
    AnularIn,
    DocumentoOut,
    DocumentoResumen,
    EmisorIn,
    EmisorOut,
    EmitirIn,
    FolioRangeIn,
    FolioRangeOut,
)
from app.services.medico import audit
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/tributario", tags=["tributario"])


def _emisor_out(em: TaxEmitter) -> EmisorOut:
    return EmisorOut(
        id=em.id, pais=em.pais, tax_id=em.tax_id, razon_social=em.razon_social,
        giro=em.giro, direccion=em.direccion, config=em.config,
    )


def _folio_out(r: TaxFolioRange) -> FolioRangeOut:
    return FolioRangeOut(
        id=r.id, tipo_documento=r.tipo_documento, serie=r.serie, desde=r.desde, hasta=r.hasta,
        siguiente=r.siguiente, disponibles=max(0, r.hasta - r.siguiente + 1), caf_ref=r.caf_ref, activo=r.activo,
    )


def _doc_resumen(d: TaxDocument) -> DocumentoResumen:
    return DocumentoResumen(
        id=d.id, pais=d.pais, jurisdiccion=d.jurisdiccion, organo=d.organo, tipo_documento=d.tipo_documento,
        codigo=d.codigo, serie=d.serie, folio=d.folio, receptor_nombre=d.receptor_nombre,
        neto=float(d.neto), impuesto=float(d.impuesto), total=float(d.total), moneda=d.moneda,
        estado=d.estado, track_id=d.track_id, emitido_at=d.emitido_at,
    )


def _doc_out(d: TaxDocument) -> DocumentoOut:
    return DocumentoOut(
        **_doc_resumen(d).model_dump(),
        receptor_tax_id=d.receptor_tax_id, exento=float(d.exento), impuesto_detalle=d.impuesto_detalle,
        items=d.items, sello=d.sello, motivo=d.motivo, referencia_id=d.referencia_id, xml=d.xml,
    )


# ─────────────────────────── tipos disponibles ───────────────────────────
@router.get("/tipos")
async def tipos_disponibles(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> dict:
    clinic_id = empresa_clinic_id(ctx)
    clinic = await db.get(Clinic, clinic_id)
    pais = clinic.pais if clinic else None
    return {"pais": pais, "tipos": conn.TIPOS_POR_PAIS.get(pais or "", []), "habilitado": await conn.is_enabled(db, clinic_id)}


# ─────────────────────────── emisor fiscal ───────────────────────────
@router.get("/emisor", response_model=EmisorOut | None)
async def ver_emisor(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> EmisorOut | None:
    clinic_id = empresa_clinic_id(ctx)
    em = (
        await db.execute(select(TaxEmitter).where(TaxEmitter.clinic_id == clinic_id, TaxEmitter.deleted_at.is_(None)))
    ).scalar_one_or_none()
    return _emisor_out(em) if em else None


@router.put("/emisor", response_model=EmisorOut)
async def upsert_emisor(
    payload: EmisorIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.CREAR)),
) -> EmisorOut:
    clinic_id = empresa_clinic_id(ctx)
    clinic = await db.get(Clinic, clinic_id)
    if clinic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clínica no encontrada")
    em = (
        await db.execute(select(TaxEmitter).where(TaxEmitter.clinic_id == clinic_id, TaxEmitter.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if em is None:
        em = TaxEmitter(clinic_id=clinic_id, pais=clinic.pais, tax_id=payload.tax_id, razon_social=payload.razon_social)
        db.add(em)
    em.pais = clinic.pais
    em.tax_id = payload.tax_id
    em.razon_social = payload.razon_social
    em.giro = payload.giro
    em.direccion = payload.direccion
    em.config = payload.config
    audit(db, ctx, clinic_id=clinic_id, accion="tributario_emisor", recurso="tax_emitter")
    await db.commit()
    await db.refresh(em)
    return _emisor_out(em)


# ─────────────────────────── folios / CAF ───────────────────────────
@router.get("/folios", response_model=list[FolioRangeOut])
async def listar_folios(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> list[FolioRangeOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (
        await db.execute(
            select(TaxFolioRange).where(TaxFolioRange.clinic_id == clinic_id, TaxFolioRange.deleted_at.is_(None)).order_by(TaxFolioRange.tipo_documento)
        )
    ).scalars().all()
    return [_folio_out(r) for r in rows]


@router.post("/folios", response_model=FolioRangeOut, status_code=status.HTTP_201_CREATED)
async def registrar_folios(
    payload: FolioRangeIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.CREAR)),
) -> FolioRangeOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.hasta < payload.desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "'hasta' debe ser >= 'desde'")
    em = await conn.get_emitter(db, clinic_id)
    rng = TaxFolioRange(
        clinic_id=clinic_id, emitter_id=em.id, tipo_documento=payload.tipo_documento, serie=payload.serie,
        desde=payload.desde, hasta=payload.hasta, siguiente=payload.desde, caf_ref=payload.caf_ref,
    )
    db.add(rng)
    audit(db, ctx, clinic_id=clinic_id, accion="tributario_folios", recurso=f"tax_folio_range:{payload.tipo_documento}")
    await db.commit()
    await db.refresh(rng)
    return _folio_out(rng)


# ─────────────────────────── documentos ───────────────────────────
@router.get("/documentos", response_model=list[DocumentoResumen])
async def listar_documentos(
    estado: str | None = None,
    tipo_documento: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> list[DocumentoResumen]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(TaxDocument).where(TaxDocument.clinic_id == clinic_id, TaxDocument.deleted_at.is_(None))
    if estado:
        q = q.where(TaxDocument.estado == estado)
    if tipo_documento:
        q = q.where(TaxDocument.tipo_documento == tipo_documento)
    rows = (await db.execute(q.order_by(TaxDocument.emitido_at.desc()))).scalars().all()
    return [_doc_resumen(d) for d in rows]


@router.post("/documentos", response_model=DocumentoOut, status_code=status.HTTP_201_CREATED)
async def emitir_documento(
    payload: EmitirIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.CREAR)),
) -> DocumentoOut:
    clinic_id = empresa_clinic_id(ctx)
    doc = await conn.emitir(
        db,
        clinic_id,
        tipo_documento=payload.tipo_documento,
        items=[it.model_dump() for it in payload.items],
        receptor=payload.receptor.model_dump() if payload.receptor else None,
        serie=payload.serie,
        appointment_id=payload.appointment_id,
        cash_payment_id=payload.cash_payment_id,
        actor_id=ctx.user_id,
    )
    audit(db, ctx, clinic_id=clinic_id, accion="tributario_emitir", recurso=f"tax_document:{doc.id}")
    await db.commit()
    await db.refresh(doc)
    return _doc_out(doc)


async def _own_doc(db: AsyncSession, clinic_id: uuid.UUID, documento_id: uuid.UUID) -> TaxDocument:
    doc = await db.get(TaxDocument, documento_id)
    if doc is None or doc.deleted_at is not None or doc.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return doc


@router.get("/documentos/{documento_id}", response_model=DocumentoOut)
async def ver_documento(
    documento_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> DocumentoOut:
    clinic_id = empresa_clinic_id(ctx)
    return _doc_out(await _own_doc(db, clinic_id, documento_id))


@router.get("/documentos/{documento_id}/estado")
async def estado_documento(
    documento_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.VER)),
) -> dict:
    clinic_id = empresa_clinic_id(ctx)
    doc = await conn.consultar(db, clinic_id, documento_id)
    return {"id": str(doc.id), "estado": doc.estado, "organo": doc.organo, "track_id": doc.track_id, "sello": doc.sello, "motivo": doc.motivo}


@router.post("/documentos/{documento_id}/anular", response_model=DocumentoOut)
async def anular_documento(
    documento_id: uuid.UUID,
    payload: AnularIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.TRIBUTARIO, Action.EDITAR)),
) -> DocumentoOut:
    clinic_id = empresa_clinic_id(ctx)
    await _own_doc(db, clinic_id, documento_id)  # 404 fuera de la clínica antes de tocar el conector
    resultado = await conn.anular(db, clinic_id, documento_id, motivo=payload.motivo, actor_id=ctx.user_id)
    audit(db, ctx, clinic_id=clinic_id, accion="tributario_anular", recurso=f"tax_document:{documento_id}")
    await db.commit()
    await db.refresh(resultado)
    return _doc_out(resultado)
