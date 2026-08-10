"""Conector tributario (Tanda 7): frontera única para emitir documentos
tributarios electrónicos según el país de la clínica.

  · Chile (`clinics.pais == "CL"`)  → DTE ante el SII (boleta/factura/NC).
  · Brasil (`clinics.pais == "BR"`) → Nota Fiscal (NFS-e municipal /
    NF-e·NFC-e estadual).

Como el resto de los conectores (Fase 8): se habilita por clínica vía
`IntegrationConfig(tipo="tributario")`, deja traza en `integration_events`, e
implementa la **forma real** del contrato con transporte simulado y determinista
(los puntos de enganche reales están documentados en cada builder de país).

Las funciones de este módulo **agregan** a la sesión y hacen `flush` pero **no
hacen commit** — el caller decide la transacción (así la emisión puede ir en el
mismo commit que el movimiento de caja que la origina)."""

import datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import ensure_enabled, log_event
from app.integrations.tributario import brasil_nf, chile_sii
from app.models.integrations import IntegrationConfig
from app.models.tax import TaxDocument, TaxEmitter, TaxFolioRange
from app.models.tenant import Clinic

TIPOS_POR_PAIS: dict[str, list[str]] = {
    "CL": ["boleta_electronica", "factura_electronica", "nota_credito"],
    "BR": ["nfse", "nfe", "nfce"],
}


async def is_enabled(db: AsyncSession, clinic_id: uuid.UUID) -> bool:
    """Chequeo blando (no lanza) para callers que emiten de forma opcional
    (p. ej. la caja): ¿está el conector tributario habilitado en la clínica?"""
    cfg = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.clinic_id == clinic_id,
                IntegrationConfig.tipo == "tributario",
                IntegrationConfig.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return cfg is not None and cfg.activo


async def get_emitter(db: AsyncSession, clinic_id: uuid.UUID) -> TaxEmitter:
    em = (
        await db.execute(
            select(TaxEmitter).where(TaxEmitter.clinic_id == clinic_id, TaxEmitter.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if em is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "La clínica no tiene emisor fiscal configurado (define /tributario/emisor)")
    return em


async def _assign_folio(db: AsyncSession, emitter: TaxEmitter, tipo_documento: str, serie: str | None) -> tuple[int, str | None]:
    """Toma el próximo folio del rango autorizado (CAF en Chile / serie en
    Brasil), avanzando el puntero bajo bloqueo de fila para evitar folios
    duplicados ante concurrencia."""
    q = (
        select(TaxFolioRange)
        .where(
            TaxFolioRange.emitter_id == emitter.id,
            TaxFolioRange.tipo_documento == tipo_documento,
            TaxFolioRange.activo.is_(True),
            TaxFolioRange.deleted_at.is_(None),
        )
        .order_by(TaxFolioRange.desde.asc())
        .with_for_update()
    )
    if serie is not None:
        q = q.where(TaxFolioRange.serie == serie)
    rng = (await db.execute(q)).scalars().first()
    if rng is None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"No hay folios disponibles para '{tipo_documento}' (registra un rango/CAF)")
    if rng.siguiente > rng.hasta:
        raise HTTPException(status.HTTP_409_CONFLICT, f"El rango de folios de '{tipo_documento}' está agotado (folio {rng.siguiente} > {rng.hasta})")
    folio = rng.siguiente
    rng.siguiente = folio + 1
    return folio, rng.caf_ref


async def emitir(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    *,
    tipo_documento: str,
    items: list[dict],
    receptor: dict | None = None,
    serie: str | None = None,
    appointment_id: uuid.UUID | None = None,
    cash_payment_id: uuid.UUID | None = None,
    ledger_entry_id: uuid.UUID | None = None,
    referencia_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    referencia_dte: dict | None = None,
) -> TaxDocument:
    """Emite un documento tributario para la clínica. Enruta por país, asigna
    folio, construye el documento (forma real) y lo persiste `aceptado`."""
    await ensure_enabled(db, clinic_id, "tributario")
    if not items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El documento necesita al menos una línea")

    clinic = await db.get(Clinic, clinic_id)
    pais = clinic.pais if clinic else None
    permitidos = TIPOS_POR_PAIS.get(pais or "", [])
    if tipo_documento not in permitidos:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{tipo_documento}' no aplica para el país {pais}. Permitidos: {permitidos or 'ninguno (país sin régimen soportado)'}",
        )

    emitter = await get_emitter(db, clinic_id)
    folio, caf_ref = await _assign_folio(db, emitter, tipo_documento, serie)
    fecha = datetime.date.today().isoformat()

    if pais == "CL":
        built = chile_sii.build_dte(
            tipo_documento=tipo_documento,
            folio=folio,
            caf_ref=caf_ref,
            emitter=emitter,
            receptor=receptor,
            items=items,
            fecha=fecha,
            referencia=referencia_dte,
        )
    else:  # BR
        built = brasil_nf.build_nf(
            tipo_documento=tipo_documento,
            numero=folio,
            serie=serie,
            emitter=emitter,
            receptor=receptor,
            items=items,
            fecha=fecha,
        )

    doc = TaxDocument(
        clinic_id=clinic_id,
        emitter_id=emitter.id,
        pais=pais,
        jurisdiccion=built["jurisdiccion"],
        organo=built["organo"],
        tipo_documento=tipo_documento,
        codigo=built["codigo"],
        serie=serie,
        folio=folio,
        receptor_tax_id=(receptor or {}).get("tax_id"),
        receptor_nombre=(receptor or {}).get("nombre"),
        neto=built["neto"],
        exento=built["exento"],
        impuesto=built["impuesto"],
        total=built["total"],
        moneda=built["moneda"],
        impuesto_detalle=built["impuesto_detalle"],
        items=items,
        estado=built["estado"],
        track_id=built["track_id"],
        sello=built["sello"],
        xml=built["xml"],
        referencia_id=referencia_id,
        appointment_id=appointment_id,
        cash_payment_id=cash_payment_id,
        ledger_entry_id=ledger_entry_id,
        emitido_at=datetime.datetime.now(datetime.timezone.utc),
        created_by=actor_id,
    )
    db.add(doc)
    await db.flush()

    log_event(
        db,
        clinic_id=clinic_id,
        tipo="tributario",
        direccion="outbound",
        estado="enviado",
        ref=f"{tipo_documento}:{folio}",
        payload={"tipo": tipo_documento, "folio": folio, "total": built["total"]},
        resultado={"organo": built["organo"], "estado": built["estado"], "track_id": built["track_id"]},
    )
    return doc


async def anular(
    db: AsyncSession,
    clinic_id: uuid.UUID,
    documento_id: uuid.UUID,
    *,
    motivo: str,
    actor_id: uuid.UUID | None = None,
) -> TaxDocument:
    """Anula un documento aceptado.

      · Chile: emite una **nota de crédito (61)** que referencia al documento
        original (CodRef=1) y lo marca `anulado`. Devuelve la NC.
      · Brasil: registra el **cancelamento** ante el órgano (protocolo de
        cancelamento) y marca el documento `anulado`. Devuelve el mismo
        documento actualizado.
    """
    await ensure_enabled(db, clinic_id, "tributario")
    doc = await db.get(TaxDocument, documento_id)
    if doc is None or doc.deleted_at is not None or doc.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    if doc.estado == "anulado":
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento ya está anulado")
    if doc.estado != "aceptado":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Solo se anula un documento aceptado (estado actual: {doc.estado})")

    if doc.pais == "CL":
        # Nota de crédito que anula la boleta/factura. Se construye sobre el NETO
        # del documento original (no sobre sus líneas, que en una boleta vienen
        # con IVA incluido): así la NC —convención factura, IVA por fuera—
        # reproduce exactamente el total anulado.
        nc = await emitir(
            db,
            clinic_id,
            tipo_documento="nota_credito",
            items=[{"descripcion": f"Anula {doc.tipo_documento} #{doc.folio}", "cantidad": 1, "precio_unitario": float(doc.neto)}],
            receptor={"tax_id": doc.receptor_tax_id, "nombre": doc.receptor_nombre} if doc.receptor_tax_id else None,
            referencia_id=doc.id,
            actor_id=actor_id,
            referencia_dte={
                "tipo": doc.codigo,
                "folio": doc.folio,
                "fecha": doc.emitido_at.date().isoformat(),
                "razon": motivo,
            },
        )
        doc.estado = "anulado"
        doc.motivo = motivo
        await db.flush()
        return nc

    # Brasil: cancelamento (sin documento inverso).
    from app.integrations.tributario.brasil_nf import _protocolo

    doc.estado = "anulado"
    doc.motivo = motivo
    detalle = dict(doc.impuesto_detalle or {})
    detalle["cancelamento_protocolo"] = _protocolo(f"CANCEL|{doc.track_id}|{motivo}")
    doc.impuesto_detalle = detalle
    log_event(
        db,
        clinic_id=clinic_id,
        tipo="tributario",
        direccion="outbound",
        estado="enviado",
        ref=f"cancelamento:{doc.folio}",
        payload={"documento_id": str(doc.id), "motivo": motivo},
        resultado={"estado": "anulado", "protocolo": detalle["cancelamento_protocolo"]},
    )
    await db.flush()
    return doc


async def consultar(db: AsyncSession, clinic_id: uuid.UUID, documento_id: uuid.UUID) -> TaxDocument:
    """Estado del documento ante el órgano. Hook real: SII `QueryEstDte` /
    SEFAZ consulta de protocolo. Aquí el estado ya está resuelto en la emisión."""
    doc = await db.get(TaxDocument, documento_id)
    if doc is None or doc.deleted_at is not None or doc.clinic_id != clinic_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Documento no encontrado")
    return doc
