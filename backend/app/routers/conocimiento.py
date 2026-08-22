"""Base de conocimiento de la clínica (72): la empresa sube PDFs/textos que la
IA usará como fuente al conversar. Todo dentro de la propia plataforma."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.knowledge import KnowledgeChunk, KnowledgeSource
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.conocimiento import BuscarIn, BuscarOut, FragmentoOut, FuenteOut, FuenteUpdate, TextoIn
from app.services import conocimiento
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/empresa/conocimiento", tags=["conocimiento"])

_MAX_BYTES = 8_000_000  # 8 MB por archivo


def _fuente_out(s: KnowledgeSource) -> FuenteOut:
    return FuenteOut(id=s.id, nombre=s.nombre, tipo=s.tipo, estado=s.estado, n_chunks=s.n_chunks, activo=s.activo, fecha=s.created_at)


@router.get("", response_model=list[FuenteOut])
async def listar_fuentes(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.VER)),
) -> list[FuenteOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(KnowledgeSource).where(KnowledgeSource.clinic_id == clinic_id, KnowledgeSource.deleted_at.is_(None)).order_by(KnowledgeSource.created_at.desc()))).scalars().all()
    return [_fuente_out(s) for s in rows]


@router.post("/texto", response_model=FuenteOut, status_code=status.HTTP_201_CREATED)
async def subir_texto(
    payload: TextoIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.EDITAR)),
) -> FuenteOut:
    clinic_id = empresa_clinic_id(ctx)
    source = await conocimiento.ingerir(db, clinic_id=clinic_id, created_by=ctx.user_id, nombre=payload.nombre, texto=payload.texto, tipo="texto")
    await db.commit()
    await db.refresh(source)
    return _fuente_out(source)


@router.post("/pdf", response_model=FuenteOut, status_code=status.HTTP_201_CREATED)
async def subir_pdf(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.EDITAR)),
) -> FuenteOut:
    clinic_id = empresa_clinic_id(ctx)
    contenido = await file.read()
    if len(contenido) > _MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El archivo es demasiado grande (máx 8 MB)")
    try:
        texto = conocimiento.extraer_texto_pdf(contenido)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No se pudo leer el PDF") from exc
    if not texto.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El PDF no tiene texto extraíble (¿es un escaneo sin OCR?)")
    source = await conocimiento.ingerir(db, clinic_id=clinic_id, created_by=ctx.user_id, nombre=file.filename or "Documento.pdf", texto=texto, tipo="pdf")
    await db.commit()
    await db.refresh(source)
    return _fuente_out(source)


async def _own_fuente(db: AsyncSession, clinic_id: uuid.UUID, sid: uuid.UUID) -> KnowledgeSource:
    s = await db.get(KnowledgeSource, sid)
    if s is None or s.clinic_id != clinic_id or s.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuente no encontrada")
    return s


@router.patch("/{sid}", response_model=FuenteOut)
async def editar_fuente(
    sid: uuid.UUID,
    payload: FuenteUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.EDITAR)),
) -> FuenteOut:
    clinic_id = empresa_clinic_id(ctx)
    s = await _own_fuente(db, clinic_id, sid)
    if payload.nombre is not None:
        s.nombre = payload.nombre
    if payload.activo is not None:
        s.activo = payload.activo
    await db.commit()
    await db.refresh(s)
    return _fuente_out(s)


@router.delete("/{sid}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_fuente(
    sid: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.EDITAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    s = await _own_fuente(db, clinic_id, sid)
    chunks = (await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.source_id == sid, KnowledgeChunk.deleted_at.is_(None)))).scalars().all()
    for c in chunks:
        await db.delete(c)
    await db.delete(s)
    await db.commit()


@router.post("/buscar", response_model=BuscarOut)
async def buscar(
    payload: BuscarIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.INFO_EMPRESA, Action.VER)),
) -> BuscarOut:
    """Previsualiza qué fragmentos recuperaría la IA para una consulta."""
    clinic_id = empresa_clinic_id(ctx)
    hits = await conocimiento.buscar(db, clinic_id, payload.consulta, k=payload.k)
    return BuscarOut(resultados=[FragmentoOut(fuente=src.nombre, texto=ch.texto, score=round(score, 4)) for score, ch, src in hits])
