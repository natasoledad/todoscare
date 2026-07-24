"""The RBAC matrix, transcribed directly from each role's spec (§ RBAC).

This captures coarse resource-level grants. Row-level ownership checks
("solo su ficha", "solo pacientes atendidos", "solo lo autorizado") are
*not* expressible as a static matrix — those are enforced in the service
layer on top of a passing `has_permission()` check, and are called out in
comments below wherever the spec says "solo propios" / "solo atendidos" /
"según config.". Business endpoints land in later phases; this module is
the shared foundation they'll all call into.
"""

from app.rbac.permissions import Action, Resource, RoleCode

V, C, E, D = Action.VER, Action.CREAR, Action.EDITAR, Action.ELIMINAR

_ADMIN_MATRIX: dict[Resource, set[Action]] = {
    # Spec Administrador §4
    Resource.CLINICAS_SUCURSALES: {V, C, E, D},  # D = baja lógica
    Resource.USUARIOS_ROLES: {V, C, E, D},  # D = baja lógica
    Resource.PLANES_PRECIOS: {V, C, E, D},
    Resource.TYC_PAIS: {V, C, E},  # C = nueva versión, E = nueva versión; no D (histórico)
    Resource.LEDGER_FINANCIERO: {V, C},  # C = automático (sistema, no manual); nunca E/D
    Resource.FICHA_CLINICA_METADATOS: {V},  # solo metadatos/auditoría — nunca contenido clínico
    # Integraciones (Fase 8): el admin habilita/deshabilita conectores y ve su traza
    Resource.INTEGRACIONES: {V, C, E, D},
    # CRM (Spec CRM §7 — fila Admin)
    Resource.CRM_CONSOLIDADO_GLOBAL: {V},
    Resource.CRM_KPIS_CLINICA: {V},
    Resource.CRM_CONCILIAR: {V, E},
    Resource.CRM_EXPORTAR_ERP: {V},
    Resource.CRM_CAMPANAS: {V, C, E, D},  # gestión de marketing digital
}

ROLE_PERMISSIONS: dict[RoleCode, dict[Resource, set[Action]]] = {
    # super_admin / clinic_admin / branch_admin share the matrix; scope
    # (which clinics/branches it applies to) comes from RoleAssignment.
    RoleCode.SUPER_ADMIN: _ADMIN_MATRIX,
    RoleCode.CLINIC_ADMIN: _ADMIN_MATRIX,
    RoleCode.BRANCH_ADMIN: _ADMIN_MATRIX,
    RoleCode.EMPRESA: {
        # Spec Empresa Cliente §3
        Resource.CLINIC_AGENDAS: {V, C, E, D},
        Resource.CATALOGO_PRECIOS: {V, C, E, D},  # D = baja lógica
        Resource.PROMOCIONES: {V, C, E, D},
        Resource.INFO_EMPRESA: {V, E},  # sin C/D — el registro ya existe (es la clínica misma)
        Resource.FUNCIONARIOS_B2B: {V, C, E, D},  # C = alta, D = baja
        # CRM (Spec CRM §7 — fila Empresa/Clínica)
        Resource.CRM_KPIS_CLINICA: {V},
        Resource.CRM_CAMPANAS: {V, C, E, D},  # la clínica gestiona su marketing digital
        # CRM_CONCILIAR: "Según config." en la spec — no se otorga por
        # defecto; requiere una config explícita por clínica (abierto en
        # Spec CRM §10, no definido todavía).
    },
    RoleCode.MEDICO: {
        # Spec Medico §3
        Resource.OWN_AGENDA: {V, C, E, D},  # C = bloqueos propios
        Resource.PRONTUARIO_ATENDIDOS: {V, C, E},  # E = enmienda auditada; nunca D
        Resource.PRESCRIPCIONES: {V, C, E},  # E = anula + reemite; nunca D real
        Resource.ORDENES_EXAMEN: {V, C, E, D},  # E = solo pendientes, D = cancela pendientes
        Resource.LIQUIDACION_PROPIA: {V},
    },
    RoleCode.PACIENTE: {
        # Spec Paciente §3
        Resource.OWN_MEDICAL_RECORD: {V, C, E},  # E = solo campos opcionales; nunca D
        Resource.OWN_EXAM_RESULTS: {V, C},  # C = subir; nunca E/D
        Resource.OWN_APPOINTMENTS: {V, C, E, D},  # E = reagenda, D = cancela
        Resource.DEPENDIENTES: {V, C, E, D},  # C = vincular, D = desvincular
        Resource.WALLET: {V, E},  # E = usar saldo; nunca C/D directo
        Resource.CATALOGO_PRECIOS: {V},  # solo lectura — ve precios/config de su clínica, no los administra
    },
    RoleCode.ASEGURADORA: {
        # Spec Aseguradora Prestador §3
        Resource.CONVENIOS_ARANCELES: {V, C, E, D},  # E = versión, D = baja lógica
        Resource.PADRON_AFILIADOS: {V, C, E, D},  # C = alta, D = baja
        Resource.AUTORIZACIONES: {V, E},  # E = resolver (aprobar/rechazar); sin C (la solicitud la origina el flujo)/D
        Resource.LIQUIDACIONES_ASEGURADORA: {V, E},  # E = conciliar/pagar; sin C/D
        Resource.FICHA_AFILIADO_AUTORIZADA: {V},  # solo lo autorizado y auditado
    },
}


def can(role: RoleCode, resource: Resource, action: Action) -> bool:
    return action in ROLE_PERMISSIONS.get(role, {}).get(resource, set())
