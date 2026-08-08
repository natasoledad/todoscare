"""Tanda 6 — Gestión CRM de la clínica: tareas de gestión, encuestas de
satisfacción y plantillas de mensaje. Rol Empresa/Clínica (permiso CRM_CAMPANAS).

El envío real de encuestas/mensajes por correo o WhatsApp queda para la capa de
integraciones (Resend/WhatsApp); aquí se modela el ciclo y las métricas.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.marketing import CrmTask, MessageTemplate, SatisfactionSurvey
from app.rbac.deps import require
from app.rbac.permissions import Action, Resource
from app.routers.empresa import empresa_clinic_id
from app.schemas.crm_gestion import (
    EncuestaIn,
    EncuestaOut,
    EncuestaResumen,
    PlantillaIn,
    PlantillaOut,
    PlantillaUpdate,
    ResponderEncuestaIn,
    TareaIn,
    TareaOut,
    TareaUpdate,
)
from app.services.medico import audit
from app.tenancy.context import TenantContext

router = APIRouter(prefix="/crm", tags=["crm-gestion"])


# ─────────────────────────── tareas de gestión ───────────────────────────
def _tarea_out(t: CrmTask) -> TareaOut:
    return TareaOut(id=t.id, titulo=t.titulo, descripcion=t.descripcion, patient_id=t.patient_id, estado=t.estado, vencimiento=t.vencimiento, fecha=t.created_at)


@router.get("/tareas", response_model=list[TareaOut])
async def listar_tareas(
    estado: str | None = None,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.VER)),
) -> list[TareaOut]:
    clinic_id = empresa_clinic_id(ctx)
    q = select(CrmTask).where(CrmTask.clinic_id == clinic_id, CrmTask.deleted_at.is_(None))
    if estado in ("pendiente", "hecha"):
        q = q.where(CrmTask.estado == estado)
    rows = (await db.execute(q.order_by(CrmTask.created_at.desc()))).scalars().all()
    return [_tarea_out(t) for t in rows]


@router.post("/tareas", response_model=TareaOut, status_code=status.HTTP_201_CREATED)
async def crear_tarea(
    payload: TareaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.CREAR)),
) -> TareaOut:
    clinic_id = empresa_clinic_id(ctx)
    t = CrmTask(clinic_id=clinic_id, **payload.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _tarea_out(t)


async def _own_tarea(db: AsyncSession, clinic_id: uuid.UUID, tarea_id: uuid.UUID) -> CrmTask:
    t = await db.get(CrmTask, tarea_id)
    if t is None or t.deleted_at is not None or t.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tarea no encontrada")
    return t


@router.patch("/tareas/{tarea_id}", response_model=TareaOut)
async def actualizar_tarea(
    tarea_id: uuid.UUID,
    payload: TareaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.EDITAR)),
) -> TareaOut:
    clinic_id = empresa_clinic_id(ctx)
    t = await _own_tarea(db, clinic_id, tarea_id)
    data = payload.model_dump(exclude_none=True)
    if "estado" in data and data["estado"] not in ("pendiente", "hecha"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Estado inválido (pendiente | hecha)")
    for k, v in data.items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return _tarea_out(t)


@router.delete("/tareas/{tarea_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_tarea(
    tarea_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    t = await _own_tarea(db, clinic_id, tarea_id)
    await db.delete(t)
    await db.commit()


# ─────────────────────────── encuestas de satisfacción ───────────────────────────
def _encuesta_out(s: SatisfactionSurvey) -> EncuestaOut:
    return EncuestaOut(id=s.id, paciente_nombre=s.paciente_nombre, estado=s.estado, score=s.score, comentario=s.comentario, fecha=s.created_at, respondida_at=s.respondida_at)


@router.get("/encuestas", response_model=list[EncuestaOut])
async def listar_encuestas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.VER)),
) -> list[EncuestaOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(SatisfactionSurvey).where(SatisfactionSurvey.clinic_id == clinic_id, SatisfactionSurvey.deleted_at.is_(None)).order_by(SatisfactionSurvey.created_at.desc()))).scalars().all()
    return [_encuesta_out(s) for s in rows]


@router.get("/encuestas/resumen", response_model=EncuestaResumen)
async def resumen_encuestas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.VER)),
) -> EncuestaResumen:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(SatisfactionSurvey.estado, SatisfactionSurvey.score).where(SatisfactionSurvey.clinic_id == clinic_id, SatisfactionSurvey.deleted_at.is_(None)))).all()
    enviadas = len(rows)
    scores = [sc for est, sc in rows if est == "respondida" and sc is not None]
    respondidas = len(scores)
    promedio = round(sum(scores) / respondidas, 1) if respondidas else None
    nps = None
    if respondidas:
        promoters = sum(1 for s in scores if s >= 9)
        detractors = sum(1 for s in scores if s <= 6)
        nps = round((promoters - detractors) / respondidas * 100)
    tasa = round(respondidas / enviadas * 100, 1) if enviadas else 0.0
    return EncuestaResumen(enviadas=enviadas, respondidas=respondidas, tasa_respuesta=tasa, promedio=promedio, nps=nps)


@router.post("/encuestas", response_model=EncuestaOut, status_code=status.HTTP_201_CREATED)
async def enviar_encuesta(
    payload: EncuestaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.CREAR)),
) -> EncuestaOut:
    clinic_id = empresa_clinic_id(ctx)
    s = SatisfactionSurvey(clinic_id=clinic_id, patient_id=payload.patient_id, paciente_nombre=payload.paciente_nombre, appointment_id=payload.appointment_id, estado="enviada")
    db.add(s)
    audit(db, ctx, clinic_id=clinic_id, accion="enviar_encuesta", recurso="satisfaction_survey")
    await db.commit()
    await db.refresh(s)
    return _encuesta_out(s)


@router.post("/encuestas/{encuesta_id}/responder", response_model=EncuestaOut)
async def responder_encuesta(
    encuesta_id: uuid.UUID,
    payload: ResponderEncuestaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.EDITAR)),
) -> EncuestaOut:
    clinic_id = empresa_clinic_id(ctx)
    s = await db.get(SatisfactionSurvey, encuesta_id)
    if s is None or s.deleted_at is not None or s.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Encuesta no encontrada")
    s.estado = "respondida"
    s.score = payload.score
    s.comentario = payload.comentario
    s.respondida_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return _encuesta_out(s)


# ─────────────────────────── plantillas de mensaje ───────────────────────────
def _plantilla_out(p: MessageTemplate) -> PlantillaOut:
    return PlantillaOut(id=p.id, nombre=p.nombre, canal=p.canal, asunto=p.asunto, cuerpo=p.cuerpo)


@router.get("/plantillas", response_model=list[PlantillaOut])
async def listar_plantillas(
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.VER)),
) -> list[PlantillaOut]:
    clinic_id = empresa_clinic_id(ctx)
    rows = (await db.execute(select(MessageTemplate).where(MessageTemplate.clinic_id == clinic_id, MessageTemplate.deleted_at.is_(None)).order_by(MessageTemplate.nombre))).scalars().all()
    return [_plantilla_out(p) for p in rows]


@router.post("/plantillas", response_model=PlantillaOut, status_code=status.HTTP_201_CREATED)
async def crear_plantilla(
    payload: PlantillaIn,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.CREAR)),
) -> PlantillaOut:
    clinic_id = empresa_clinic_id(ctx)
    if payload.canal not in ("email", "whatsapp"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Canal inválido (email | whatsapp)")
    p = MessageTemplate(clinic_id=clinic_id, **payload.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _plantilla_out(p)


async def _own_plantilla(db: AsyncSession, clinic_id: uuid.UUID, plantilla_id: uuid.UUID) -> MessageTemplate:
    p = await db.get(MessageTemplate, plantilla_id)
    if p is None or p.deleted_at is not None or p.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plantilla no encontrada")
    return p


@router.patch("/plantillas/{plantilla_id}", response_model=PlantillaOut)
async def actualizar_plantilla(
    plantilla_id: uuid.UUID,
    payload: PlantillaUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.EDITAR)),
) -> PlantillaOut:
    clinic_id = empresa_clinic_id(ctx)
    p = await _own_plantilla(db, clinic_id, plantilla_id)
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _plantilla_out(p)


@router.delete("/plantillas/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT)
async def eliminar_plantilla(
    plantilla_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    ctx: TenantContext = Depends(require(Resource.CRM_CAMPANAS, Action.ELIMINAR)),
) -> None:
    clinic_id = empresa_clinic_id(ctx)
    p = await _own_plantilla(db, clinic_id, plantilla_id)
    await db.delete(p)
    await db.commit()
