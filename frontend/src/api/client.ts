import type {
  AdminKpis,
  AuditEntry,
  AuthOut,
  Bloque,
  Branch,
  Afiliado,
  Arancel as ArancelAseg,
  AseguradoraKpis,
  Autorizacion,
  Cierre,
  ClinicAdmin,
  Cita,
  CitaMedico,
  ClinicPublic,
  Convenio,
  CrmAsientoExport,
  CrmConsolidado,
  CrmDetalleClinica,
  CrmLiquidacion,
  Dependent,
  EmergencyQr,
  EmpresaKpis,
  Examen,
  FichaAfiliado,
  FichaPaciente,
  FichaUpdateInput,
  LiquidacionAseg,
  RedClinica,
  FinanzasResumen,
  Funcionario,
  Hospitalizacion,
  InfoEmpresa,
  LedgerEntryAdmin,
  Liquidacion,
  Me,
  Medicamento,
  Movimiento,
  Odontograma,
  OnboardingInput,
  Orden,
  PatientMe,
  PlanAdmin,
  PrescripcionResult,
  Profesional,
  Promocion,
  Prontuario,
  QrAccessLog,
  RegisterInput,
  ReservaInput,
  Servicio,
  ServicioAdmin,
  Slot,
  TycAdmin,
  TycVersion,
  UsuarioAdmin,
  Wallet,
} from './types';

const TOKEN_KEY = 'todoscare_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(path, { ...options, headers });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json()).detail;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body ? JSON.stringify(body) : undefined });
const patch = <T>(path: string, body?: unknown) => request<T>(path, { method: 'PATCH', body: body ? JSON.stringify(body) : undefined });
const del = (path: string) => request<void>(path, { method: 'DELETE' });

export const api = {
  clinics: {
    public: () => get<ClinicPublic[]>('/clinics/public'),
  },
  tyc: {
    latest: (pais: string) => get<TycVersion>(`/tyc/latest?pais=${encodeURIComponent(pais)}`),
  },
  auth: {
    login: (correo: string, password: string) => post<AuthOut>('/auth/login', { email: correo, password }),
    me: () => get<Me>('/auth/me'),
  },
  patients: {
    register: (input: RegisterInput) => post<AuthOut>('/patients/register', input),
    me: () => get<PatientMe>('/patients/me'),
    onboarding: (input: OnboardingInput) => post<PatientMe>('/patients/onboarding', input),
    updateFicha: (input: FichaUpdateInput) => patch<PatientMe>('/patients/me/ficha', input),
  },
  agenda: {
    servicios: () => get<Servicio[]>('/agenda/servicios'),
    disponibilidad: (serviceId: string) => get<Slot[]>(`/agenda/disponibilidad?service_id=${serviceId}`),
    reservar: (input: ReservaInput) => post<Cita>('/agenda/reservar', input),
    mias: () => get<Cita[]>('/agenda/mias'),
    cancelar: (id: string) => patch<Cita>(`/agenda/${id}/cancelar`),
  },
  salud: {
    examenes: () => get<Examen[]>('/salud/examenes'),
    subirExamen: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return request<Examen>('/salud/examenes/subir', { method: 'POST', body: form });
    },
    dental: () => get<Odontograma>('/salud/dental'),
    hospitalizaciones: () => get<Hospitalizacion[]>('/salud/hospitalizaciones'),
    qr: () => get<EmergencyQr>('/salud/qr'),
    qrAccesos: () => get<QrAccessLog[]>('/salud/qr/mis-accesos'),
    resolverQr: (token: string) => get<{ patient_nombre: string; resumen: EmergencyQr['resumen'] }>(`/salud/qr/resolver/${token}`),
  },
  farmacia: {
    medicamentos: () => get<Medicamento[]>('/farmacia/medicamentos'),
  },
  billetera: {
    balance: () => get<Wallet>('/billetera'),
    movimientos: () => get<Movimiento[]>('/billetera/movimientos'),
    pagarCashback: (monto: number) => post<Wallet>('/billetera/pagar-cashback', { monto }),
    canjearPuntos: (puntos: number) => post<Wallet>('/billetera/canjear-puntos', { puntos }),
  },
  medico: {
    agenda: (fecha?: string) => get<CitaMedico[]>(`/medico/agenda${fecha ? `?fecha=${fecha}` : ''}`),
    ficha: (patientId: string) => get<FichaPaciente>(`/medico/pacientes/${patientId}/ficha`),
    prontuario: (citaId: string) => get<Prontuario[]>(`/medico/citas/${citaId}/prontuario`),
    registrarAtencion: (citaId: string, body: { motivo: string; evolucion?: string; diagnostico?: string }) =>
      post<Prontuario>(`/medico/citas/${citaId}/atencion`, body),
    enmendar: (recordId: string, nota: string) => patch<Prontuario>(`/medico/prontuario/${recordId}/enmienda`, { nota }),
    prescribir: (citaId: string, items: { medicamento: string; cantidad?: string; indicaciones?: string }[], confirmarAlertas: boolean) =>
      post<PrescripcionResult>(`/medico/citas/${citaId}/prescripcion`, { items, confirmar_alertas: confirmarAlertas }),
    ordenExamen: (citaId: string, tipo: 'laboratorio' | 'imagenes') => post<Orden>(`/medico/citas/${citaId}/orden-examen`, { tipo }),
    odontograma: (patientId: string, piezas: Record<string, { estado: string }>) =>
      request<{ piezas: Record<string, { estado: string }> }>(`/medico/pacientes/${patientId}/odontograma`, { method: 'PUT', body: JSON.stringify({ piezas }) }),
    cerrar: (citaId: string) => post<Cierre>(`/medico/citas/${citaId}/cerrar`),
    noShow: (citaId: string) => patch<Cierre>(`/medico/citas/${citaId}/no-show`),
    liquidaciones: () => get<Liquidacion[]>('/medico/liquidaciones'),
  },
  empresa: {
    inicio: () => get<EmpresaKpis>('/empresa/inicio'),
    profesionales: () => get<Profesional[]>('/empresa/profesionales'),
    sucursales: () => get<Branch[]>('/empresa/sucursales'),
    agendas: (professionalId?: string) => get<Bloque[]>(`/empresa/agendas${professionalId ? `?professional_id=${professionalId}` : ''}`),
    crearBloque: (body: { professional_id: string; branch_id: string; inicio: string; fin: string; reglas?: Record<string, unknown> }) =>
      post<Bloque>('/empresa/agendas', body),
    eliminarBloque: (id: string) => del(`/empresa/agendas/${id}`),
    servicios: () => get<ServicioAdmin[]>('/empresa/servicios'),
    crearServicio: (body: { nombre: string; precio: number; duracion_min: number; specialty_id?: string }) => post<ServicioAdmin>('/empresa/servicios', body),
    editarServicio: (id: string, body: { nombre?: string; precio?: number; duracion_min?: number; activo?: boolean }) => patch<ServicioAdmin>(`/empresa/servicios/${id}`, body),
    eliminarServicio: (id: string) => del(`/empresa/servicios/${id}`),
    promociones: () => get<Promocion[]>('/empresa/promociones'),
    crearPromo: (body: { nombre: string; descuento?: string; segmento?: string; estado?: string }) => post<Promocion>('/empresa/promociones', body),
    editarPromo: (id: string, body: { estado?: string; nombre?: string; descuento?: string }) => patch<Promocion>(`/empresa/promociones/${id}`, body),
    eliminarPromo: (id: string) => del(`/empresa/promociones/${id}`),
    info: () => get<InfoEmpresa>('/empresa/info'),
    editarInfo: (body: { razon_social?: string; responsable_sanitario?: string }) => patch<InfoEmpresa>('/empresa/info', body),
    funcionarios: () => get<Funcionario[]>('/empresa/funcionarios'),
    altaFuncionario: (correo: string) => post<Funcionario>('/empresa/funcionarios', { correo }),
    bajaFuncionario: (id: string) => del(`/empresa/funcionarios/${id}`),
  },
  admin: {
    inicio: () => get<AdminKpis>('/admin/inicio'),
    clinicas: () => get<ClinicAdmin[]>('/admin/clinicas'),
    altaClinica: (body: { razon_social: string; pais: string; responsable_sanitario?: string; sucursal_nombre: string; admin_nombre: string; admin_correo: string; admin_password: string }) =>
      post<{ clinic_id: string; branch_id: string; admin_user_id: string }>('/admin/clinicas', body),
    bajaClinica: (id: string) => del(`/admin/clinicas/${id}`),
    usuarios: () => get<UsuarioAdmin[]>('/admin/usuarios'),
    crearUsuario: (body: { nombre: string; correo: string; password: string; role: string; clinic_id?: string }) => post<UsuarioAdmin>('/admin/usuarios', body),
    planes: () => get<PlanAdmin[]>('/admin/planes'),
    crearPlan: (body: { tipo: string; esfera?: string; nombre: string; precio: number }) => post<PlanAdmin>('/admin/planes', body),
    tyc: () => get<TycAdmin[]>('/admin/tyc'),
    publicarTyc: (body: { pais: string; version: string; contenido: string }) => post<TycAdmin>('/admin/tyc', body),
    finanzas: () => get<FinanzasResumen>('/admin/finanzas'),
    ledger: () => get<LedgerEntryAdmin[]>('/admin/finanzas/ledger'),
    auditoria: () => get<AuditEntry[]>('/admin/auditoria'),
  },
  crm: {
    consolidado: (period?: string) => get<CrmConsolidado>(`/crm/consolidado${period ? `?period=${period}` : ''}`),
    miClinica: (period?: string) => get<CrmDetalleClinica>(`/crm/mi-clinica${period ? `?period=${period}` : ''}`),
    detalleClinica: (clinicId: string, period?: string) => get<CrmDetalleClinica>(`/crm/clinicas/${clinicId}${period ? `?period=${period}` : ''}`),
    liquidaciones: (period?: string) => get<CrmLiquidacion[]>(`/crm/liquidaciones${period ? `?period=${period}` : ''}`),
    conciliar: (splitId: string) => post<{ split_id: string; estado: string; conciliado_at: string | null }>(`/crm/liquidaciones/${splitId}/conciliar`),
    exportar: (period?: string) => get<CrmAsientoExport[]>(`/crm/exportar${period ? `?period=${period}` : ''}`),
  },
  aseguradora: {
    inicio: () => get<AseguradoraKpis>('/aseguradora/inicio'),
    convenios: () => get<Convenio[]>('/aseguradora/convenios'),
    aranceles: (agreementId: string) => get<ArancelAseg[]>(`/aseguradora/convenios/${agreementId}/aranceles`),
    crearArancel: (agreementId: string, body: { service_id: string; cobertura_pct: number; copago: number }) => post<ArancelAseg>(`/aseguradora/convenios/${agreementId}/aranceles`, body),
    afiliados: () => get<Afiliado[]>('/aseguradora/afiliados'),
    altaAfiliado: (body: { documento_identidad: string; plan_cobertura?: string; vigencia_desde?: string; vigencia_hasta?: string }) => post<Afiliado>('/aseguradora/afiliados', body),
    bajaAfiliado: (id: string) => del(`/aseguradora/afiliados/${id}`),
    autorizaciones: (estado?: string) => get<Autorizacion[]>(`/aseguradora/autorizaciones${estado ? `?estado=${estado}` : ''}`),
    resolver: (id: string, decision: 'aprobar' | 'rechazar' | 'pedir_info', motivo?: string) =>
      post<{ authorization_id: string; estado: string; motivo_rechazo: string | null }>(`/aseguradora/autorizaciones/${id}/resolver`, { decision, motivo }),
    liquidaciones: () => get<LiquidacionAseg[]>('/aseguradora/liquidaciones'),
    generarLiquidacion: (agreementId: string, periodo: string) => post<{ settlement_id: string; periodo: string; monto: number; estado: string }>(`/aseguradora/convenios/${agreementId}/liquidaciones`, { periodo }),
    pagarLiquidacion: (id: string) => post<{ settlement_id: string; estado: string; pagado_at: string | null }>(`/aseguradora/liquidaciones/${id}/pagar`),
    red: () => get<RedClinica[]>('/aseguradora/red'),
    ficha: (patientId: string) => get<FichaAfiliado>(`/aseguradora/afiliados/${patientId}/ficha`),
  },
};

export type { Dependent };
