"""Conector 'ia_clinica' — la IA que lee los documentos del paciente (punto 72).

Enganche real: OCR + un LLM que extrae valores del examen y propone campos de
la ficha + una fecha de próximo control. Aquí el análisis se resuelve con
reglas deterministas sobre el nombre/tipo del documento, de modo que el flujo
end-to-end (subir → sugerencia → aplicar a la ficha → próximo control →
recordatorio) sea verificable sin depender de un modelo externo.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integrations import IntegrationConfig

TIPO = "ia_clinica"


async def config_activa(db: AsyncSession, clinic_id: uuid.UUID) -> bool:
    """¿La clínica tiene habilitado el conector de IA clínica? (no lanza: la
    subida de un examen no debe fallar porque la IA esté apagada)."""
    cfg = (
        await db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.clinic_id == clinic_id,
                IntegrationConfig.tipo == TIPO,
                IntegrationConfig.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    return cfg is not None and cfg.activo


# Reglas: palabra clave en el nombre del documento -> (resumen, parche de ficha,
# meses hasta el próximo control sugerido).
_REGLAS: list[tuple[tuple[str, ...], str, dict, int]] = [
    (("presion", "presión", "arterial", "cardio", "ecg", "electrocardio"),
     "Documento cardiovascular: se recomienda seguimiento de presión arterial.",
     {"seguimiento_cardiovascular": True}, 3),
    (("glicemia", "glucosa", "glucemia", "hba1c", "diabet"),
     "Perfil metabólico: control de glicemia recomendado.",
     {"seguimiento_glicemia": True}, 6),
    (("hemograma", "sangre", "perfil", "colesterol", "lipid"),
     "Examen de laboratorio general incorporado a la ficha.",
     {"ultimo_laboratorio": "cargado"}, 12),
    (("radiograf", "rx", "panoram", "imagen", "scanner", "tac", "resonancia"),
     "Estudio de imágenes incorporado a la ficha.",
     {"ultima_imagen": "cargada"}, 12),
]

_DEFAULT = ("Documento clínico incorporado a tu ficha.", {"documentos_cargados": True}, 12)


def analizar_examen(nombre: str) -> dict:
    """Devuelve {resumen, hallazgos, proximo_control_meses} para un documento."""
    t = (nombre or "").lower()
    for claves, resumen, hallazgos, meses in _REGLAS:
        if any(k in t for k in claves):
            return {"resumen": resumen, "hallazgos": dict(hallazgos), "proximo_control_meses": meses}
    resumen, hallazgos, meses = _DEFAULT
    return {"resumen": resumen, "hallazgos": dict(hallazgos), "proximo_control_meses": meses}
