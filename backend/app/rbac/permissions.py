from enum import Enum


class RoleCode(str, Enum):
    """Matches the `roles.code` seed rows. clinic_admin/branch_admin share the
    Administrador permission set with super_admin — what differs is *scope*,
    carried by RoleAssignment.clinic_id/branch_id, not the resource grants
    (Spec Administrador §2 "Sub-roles de administración")."""

    SUPER_ADMIN = "super_admin"
    CLINIC_ADMIN = "clinic_admin"
    BRANCH_ADMIN = "branch_admin"
    MEDICO = "medico"
    EMPRESA = "empresa"
    PACIENTE = "paciente"
    ASEGURADORA = "aseguradora"


class Action(str, Enum):
    VER = "ver"
    CREAR = "crear"
    EDITAR = "editar"
    ELIMINAR = "eliminar"


class Resource(str, Enum):
    # --- Administrador (Spec Administrador §4) ---
    CLINICAS_SUCURSALES = "clinicas_sucursales"
    USUARIOS_ROLES = "usuarios_roles"
    PLANES_PRECIOS = "planes_precios"
    TYC_PAIS = "tyc_pais"
    LEDGER_FINANCIERO = "ledger_financiero"
    FICHA_CLINICA_METADATOS = "ficha_clinica_metadatos"  # admin: solo metadatos/auditoría, nunca contenido

    # --- Empresa / Cliente (Spec Empresa Cliente §3) ---
    CLINIC_AGENDAS = "clinic_agendas"
    CATALOGO_PRECIOS = "catalogo_precios"
    PROMOCIONES = "promociones"
    INFO_EMPRESA = "info_empresa"
    FUNCIONARIOS_B2B = "funcionarios_b2b"

    # --- Médico (Spec Medico §3) ---
    OWN_AGENDA = "own_agenda"
    PRONTUARIO_ATENDIDOS = "prontuario_atendidos"  # ficha clínica completa, solo pacientes atendidos
    PRESCRIPCIONES = "prescripciones"
    ORDENES_EXAMEN = "ordenes_examen"
    LIQUIDACION_PROPIA = "liquidacion_propia"

    # --- Paciente (Spec Paciente §3) ---
    OWN_MEDICAL_RECORD = "own_medical_record"
    OWN_EXAM_RESULTS = "own_exam_results"
    OWN_APPOINTMENTS = "own_appointments"
    DEPENDIENTES = "dependientes"
    WALLET = "wallet"

    # --- CRM (Spec CRM Clinicas §7) ---
    CRM_CONSOLIDADO_GLOBAL = "crm_consolidado_global"
    CRM_KPIS_CLINICA = "crm_kpis_clinica"
    CRM_CONCILIAR = "crm_conciliar"
    CRM_EXPORTAR_ERP = "crm_exportar_erp"
    CRM_CAMPANAS = "crm_campanas"  # gestión de marketing digital

    # --- Aseguradora / Prestador (Spec Aseguradora Prestador §3) ---
    CONVENIOS_ARANCELES = "convenios_aranceles"
    PADRON_AFILIADOS = "padron_afiliados"
    AUTORIZACIONES = "autorizaciones"
    LIQUIDACIONES_ASEGURADORA = "liquidaciones_aseguradora"
    FICHA_AFILIADO_AUTORIZADA = "ficha_afiliado_autorizada"  # solo lo autorizado y auditado

    # --- Integraciones (Fase 8: conectores externos, gestionados por Admin) ---
    INTEGRACIONES = "integraciones"
