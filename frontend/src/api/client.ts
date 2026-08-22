import type {
  AgendaDia,
  Caja,
  CajaDetalle,
  CitaAgenda,
  Desempeno,
  DocumentoClinico,
  MiFirma,
  Evolucion,
  FichaEsp,
  CampoFicha,
  Vademecum,
  RecetaPlantilla,
  RecetaItem,
  Cie10Item,
  Diagnostico,
  OdontogramaPiezas,
  OdontogramaCatalogo,
  BloqueDoc,
  PlantillaDoc,
  DocumentoPaciente,
  Encuesta,
  EncuestaResumen,
  PacienteLista,
  Periodontograma,
  PerioDatos,
  PerioCatalogo,
  TimelineEvento,
  SugerenciaIA,
  RecordatorioIA,
  ChatIA,
  ConsultaIA,
  AgendarIA,
  Proveedor,
  CentroCosto,
  Bodega,
  InsumoItem,
  LoteInsumo,
  MovimientoStock,
  AlertasInventario,
  LabDental,
  LabPrestacion,
  LabOrden,
  CuentaPorPagar,
  Plantilla,
  Tarea,
  AdminKpis,
  AuditEntry,
  AuthOut,
  Bloque,
  Recinto,
  Especialidad,
  MotivoAtencion,
  HorarioTemplate,
  GenerarBloquesResult,
  BloqueoAgenda,
  LiquidacionProf,
  LiquidacionDetalle,
  MedioPago,
  EntidadFinanciera,
  GastosResumen,
  Arancel,
  ArancelCat,
  ArancelItem,
  Branch,
  Afiliado,
  Arancel as ArancelAseg,
  AseguradoraKpis,
  AsistenteRespuesta,
  Autorizacion,
  Cierre,
  ClinicAdmin,
  Cita,
  CitaMedico,
  ClinicPublic,
  ClinicaPublica,
  SlotPublico,
  ReservaPublicaInput,
  ReservaPublicaOut,
  PrepagoPublico,
  AgendaOnlineConfig,
  AgendaOnlineDashboard,
  ReporteBib,
  AgendaKpis,
  SolicitudOnline,
  Convenio,
  CrmAsientoExport,
  CrmAtribucion,
  CrmCampana,
  CrmCampanas,
  CrmConsolidado,
  CrmDetalleClinica,
  CrmLiquidacion,
  Dependent,
  EmergencyQr,
  EmpresaKpis,
  Examen,
  FichaExport,
  FichaAfiliado,
  FichaPaciente,
  DatosCl,
  FichaUpdateInput,
  IntegracionesEstado,
  LiquidacionAseg,
  RedClinica,
  SucursalCercana,
  FinanzasResumen,
  Funcionario,
  Hospitalizacion,
  InfoEmpresa,
  FuenteConocimiento,
  FragmentoConocimiento,
  LedgerEntryAdmin,
  Liquidacion,
  Me,
  Medicamento,
  Movimiento,
  MovimientoCaja,
  TributarioTipos,
  TaxEmisor,
  TaxEmisorInput,
  TaxFolio,
  TaxDocResumen,
  TaxDoc,
  EmitirTributarioInput,
  Odontograma,
  OnboardingInput,
  Orden,
  PlanTratamiento,
  Cuota,
  CuotasResumen,
  Presupuesto,
  SignosVitales,
  PatientMe,
  PromocionPaciente,
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
  PermisoOverride,
  PermisoCatalogo,
  PermisoItem,
  PerfilAcceso,
  PerfilAsignado,
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

// Todas las llamadas cuelgan de un prefijo /api (configurable con
// VITE_API_BASE). Así las rutas del SPA (/medico, /admin, /aseguradora…)
// nunca colisionan con las de la API: en dev Vite lo proxya y en producción
// nginx lo enruta al backend. El backend en sí no lleva el prefijo (lo quita
// el proxy), por eso las pruebas de humo lo llaman sin /api.
const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/$/, '');

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
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
const put = <T>(path: string, body?: unknown) => request<T>(path, { method: 'PUT', body: body ? JSON.stringify(body) : undefined });
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
    promociones: () => get<PromocionPaciente[]>('/patients/me/promociones'),
  },
  agenda: {
    servicios: () => get<Servicio[]>('/agenda/servicios'),
    disponibilidad: (serviceId: string) => get<Slot[]>(`/agenda/disponibilidad?service_id=${serviceId}`),
    reservar: (input: ReservaInput) => post<Cita>('/agenda/reservar', input),
    mias: () => get<Cita[]>('/agenda/mias'),
    cancelar: (id: string) => patch<Cita>(`/agenda/${id}/cancelar`),
  },
  salud: {
    exportarFicha: () => get<FichaExport>('/salud/ficha'),
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
    documentos: () => get<DocumentoPaciente[]>('/salud/documentos'),
    firmarDocumento: (docId: string) => post<DocumentoPaciente>(`/salud/documentos/${docId}/firmar`),
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
    guardarDatosCl: (patientId: string, body: Partial<DatosCl>) => patch<DatosCl>(`/medico/pacientes/${patientId}/datos-cl`, body),
    prontuario: (citaId: string) => get<Prontuario[]>(`/medico/citas/${citaId}/prontuario`),
    vademecum: (q: string) => get<Vademecum[]>(`/medico/vademecum?q=${encodeURIComponent(q)}`),
    recetasPlantilla: () => get<RecetaPlantilla[]>('/medico/recetas-plantilla'),
    crearRecetaPlantilla: (body: { nombre: string; items: RecetaItem[] }) => post<RecetaPlantilla>('/medico/recetas-plantilla', body),
    editarRecetaPlantilla: (id: string, body: Partial<{ nombre: string; items: RecetaItem[]; activo: boolean }>) => patch<RecetaPlantilla>(`/medico/recetas-plantilla/${id}`, body),
    eliminarRecetaPlantilla: (id: string) => del(`/medico/recetas-plantilla/${id}`),
    fichasEspecialidad: (specialtyId?: string) => get<FichaEsp[]>(`/medico/fichas-especialidad${specialtyId ? `?specialty_id=${specialtyId}` : ''}`),
    crearFichaEsp: (body: { nombre: string; specialty_id?: string; campos: CampoFicha[] }) => post<FichaEsp>('/medico/fichas-especialidad', body),
    editarFichaEsp: (id: string, body: Partial<{ nombre: string; campos: CampoFicha[]; activo: boolean }>) => patch<FichaEsp>(`/medico/fichas-especialidad/${id}`, body),
    eliminarFichaEsp: (id: string) => del(`/medico/fichas-especialidad/${id}`),
    registrarAtencion: (citaId: string, body: { motivo: string; evolucion?: string; diagnostico?: string; contenido_extra?: Record<string, unknown> }) =>
      post<Prontuario>(`/medico/citas/${citaId}/atencion`, body),
    enmendar: (recordId: string, nota: string) => patch<Prontuario>(`/medico/prontuario/${recordId}/enmienda`, { nota }),
    prescribir: (citaId: string, items: { medicamento: string; cantidad?: string; indicaciones?: string }[], confirmarAlertas: boolean) =>
      post<PrescripcionResult>(`/medico/citas/${citaId}/prescripcion`, { items, confirmar_alertas: confirmarAlertas }),
    ordenExamen: (citaId: string, tipo: 'laboratorio' | 'imagenes') => post<Orden>(`/medico/citas/${citaId}/orden-examen`, { tipo }),
    odontograma: (patientId: string, piezas: OdontogramaPiezas) =>
      request<{ piezas: OdontogramaPiezas }>(`/medico/pacientes/${patientId}/odontograma`, { method: 'PUT', body: JSON.stringify({ piezas }) }),
    odontogramaCatalogo: () => get<OdontogramaCatalogo>('/medico/odontograma/catalogo'),
    cerrar: (citaId: string) => post<Cierre>(`/medico/citas/${citaId}/cerrar`),
    noShow: (citaId: string) => patch<Cierre>(`/medico/citas/${citaId}/no-show`),
    liquidaciones: () => get<Liquidacion[]>('/medico/liquidaciones'),
    signos: (patientId: string) => get<SignosVitales[]>(`/medico/pacientes/${patientId}/signos-vitales`),
    registrarSignos: (patientId: string, body: Partial<Omit<SignosVitales, 'id' | 'fecha'>>) =>
      post<SignosVitales>(`/medico/pacientes/${patientId}/signos-vitales`, body),
    planes: (patientId: string) => get<PlanTratamiento[]>(`/medico/pacientes/${patientId}/planes`),
    crearPlan: (patientId: string, body: { titulo: string; notas?: string; items: { descripcion: string; pieza?: string; cantidad: number; precio_unit: number }[] }) =>
      post<PlanTratamiento>(`/medico/pacientes/${patientId}/planes`, body),
    editarPlan: (planId: string, body: { titulo?: string; notas?: string; descuento_pct?: number }) => patch<PlanTratamiento>(`/medico/planes/${planId}`, body),
    cambiarEstadoPlan: (planId: string, estado: string) => patch<PlanTratamiento>(`/medico/planes/${planId}/estado`, { estado }),
    cambiarEstadoItem: (planId: string, itemId: string, estado: string) => patch<PlanTratamiento>(`/medico/planes/${planId}/items/${itemId}/estado`, { estado }),
    // Financiamiento en cuotas + presupuesto (69.19 · 69.11)
    cuotas: (planId: string) => get<CuotasResumen>(`/medico/planes/${planId}/cuotas`),
    generarCuotas: (planId: string, body: { n_cuotas: number; primer_vencimiento: string; periodicidad_dias?: number; monto_total?: number }) =>
      post<CuotasResumen>(`/medico/planes/${planId}/cuotas`, body),
    marcarCuota: (cuotaId: string, pagado: boolean) => patch<Cuota>(`/medico/cuotas/${cuotaId}`, { pagado }),
    eliminarCuotas: (planId: string) => del(`/medico/planes/${planId}/cuotas`),
    presupuesto: (planId: string) => get<Presupuesto>(`/medico/planes/${planId}/presupuesto`),
    evoluciones: (patientId: string) => get<Evolucion[]>(`/medico/pacientes/${patientId}/evoluciones`),
    crearEvolucion: (patientId: string, texto: string, recordId?: string) =>
      post<Evolucion>(`/medico/pacientes/${patientId}/evoluciones`, { texto, record_id: recordId }),
    cofirmarEvolucion: (evoId: string) => post<Evolucion>(`/medico/evoluciones/${evoId}/cofirmar`),
    anularEvolucion: (evoId: string, motivo: string) => patch<Evolucion>(`/medico/evoluciones/${evoId}/anular`, { motivo }),
    miFirma: () => get<MiFirma>('/medico/mi-firma'),
    guardarMiFirma: (firma: string | null) => put<MiFirma>('/medico/mi-firma', { firma }),
    // Diagnóstico CIE-10 (71.20)
    buscarCie10: (q: string) => get<Cie10Item[]>(`/medico/cie10?q=${encodeURIComponent(q)}`),
    diagnosticos: (patientId: string) => get<Diagnostico[]>(`/medico/pacientes/${patientId}/diagnosticos`),
    agregarDiagnostico: (patientId: string, body: { codigo: string; tipo: string; observacion?: string; record_id?: string }) =>
      post<Diagnostico>(`/medico/pacientes/${patientId}/diagnosticos`, body),
    quitarDiagnostico: (dxId: string) => del(`/medico/diagnosticos/${dxId}`),
    documentos: (patientId: string) => get<DocumentoClinico[]>(`/medico/pacientes/${patientId}/documentos`),
    crearDocumento: (patientId: string, body: { tipo: string; titulo: string; contenido?: string; template_id?: string; campos?: Record<string, string>; requiere_firma?: boolean }) => post<DocumentoClinico>(`/medico/pacientes/${patientId}/documentos`, body),
    anularDocumento: (docId: string) => patch<DocumentoClinico>(`/medico/documentos/${docId}/anular`),
    plantillasDoc: () => get<PlantillaDoc[]>('/medico/plantillas-documento'),
    crearPlantillaDoc: (body: { nombre: string; tipo: string; bloques: BloqueDoc[]; requiere_firma: boolean }) => post<PlantillaDoc>('/medico/plantillas-documento', body),
    eliminarPlantillaDoc: (id: string) => del(`/medico/plantillas-documento/${id}`),
    timeline: (patientId: string) => get<TimelineEvento[]>(`/medico/pacientes/${patientId}/timeline`),
    periodontograma: (patientId: string) => get<Periodontograma | null>(`/medico/pacientes/${patientId}/periodontograma`),
    periodontogramaCatalogo: () => get<PerioCatalogo>('/medico/periodontograma/catalogo'),
    guardarPeriodontograma: (patientId: string, datos: PerioDatos, notas?: string) =>
      post<Periodontograma>(`/medico/pacientes/${patientId}/periodontograma`, { datos, notas }),
  },
  empresa: {
    inicio: () => get<EmpresaKpis>('/empresa/inicio'),
    agenda: (fecha?: string, professionalId?: string) => {
      const p = new URLSearchParams();
      if (fecha) p.set('fecha', fecha);
      if (professionalId) p.set('professional_id', professionalId);
      const qs = p.toString();
      return get<AgendaDia>(`/empresa/agenda${qs ? `?${qs}` : ''}`);
    },
    cambiarEstadoCita: (id: string, estado: string) => patch<CitaAgenda>(`/empresa/citas/${id}/estado`, { estado }),
    pacientes: (activo?: boolean, q?: string) => {
      const p = new URLSearchParams();
      if (activo !== undefined) p.set('activo', String(activo));
      if (q) p.set('q', q);
      const qs = p.toString();
      return get<PacienteLista[]>(`/empresa/pacientes${qs ? `?${qs}` : ''}`);
    },
    cambiarEstadoPaciente: (id: string, activo: boolean) => patch<PacienteLista>(`/empresa/pacientes/${id}/estado`, { activo }),
    desempeno: (period?: string) => get<Desempeno>(`/empresa/desempeno${period ? `?period=${period}` : ''}`),
    profesionales: () => get<Profesional[]>('/empresa/profesionales'),
    sucursales: () => get<Branch[]>('/empresa/sucursales'),
    agendas: (professionalId?: string) => get<Bloque[]>(`/empresa/agendas${professionalId ? `?professional_id=${professionalId}` : ''}`),
    crearBloque: (body: { professional_id: string; branch_id: string; inicio: string; fin: string; room_id?: string; reglas?: Record<string, unknown> }) =>
      post<Bloque>('/empresa/agendas', body),
    eliminarBloque: (id: string) => del(`/empresa/agendas/${id}`),
    // especialidades + perfil del profesional + motivos (punto 54)
    especialidades: () => get<Especialidad[]>('/empresa/especialidades'),
    crearEspecialidad: (body: { nombre: string; tipo: string; icono?: string }) => post<Especialidad>('/empresa/especialidades', body),
    editarEspecialidad: (id: string, body: { nombre?: string; tipo?: string; icono?: string; activo?: boolean }) =>
      patch<Especialidad>(`/empresa/especialidades/${id}`, body),
    editarPerfilProfesional: (
      profId: string,
      body: { specialty_id?: string | null; duracion_min?: number; modalidad?: string; color?: string; comision_pct?: number | null; activo?: boolean },
    ) => patch<Profesional>(`/empresa/profesionales/${profId}/perfil`, body),
    cambiarEstadoProfesional: (profId: string, activo: boolean) => patch<Profesional>(`/empresa/profesionales/${profId}/estado`, { activo }),
    remanejarPacientes: (profId: string, destinoId: string) =>
      post<{ origen_id: string; destino_id: string; destino_nombre: string; movidas: number; conflictos: number }>(
        `/empresa/profesionales/${profId}/remanejo`, { destino_id: destinoId },
      ),
    // horario semanal recurrente (52)
    horarios: (professionalId?: string) =>
      get<HorarioTemplate[]>(`/empresa/horarios${professionalId ? `?professional_id=${professionalId}` : ''}`),
    crearHorario: (body: {
      professional_id: string; branch_id: string; dia_semana: number; hora_inicio: string; hora_fin: string;
      descanso_inicio?: string | null; descanso_fin?: string | null; modalidad?: string; capacidad?: number; room_id?: string | null;
    }) => post<HorarioTemplate>('/empresa/horarios', body),
    editarHorario: (id: string, body: Record<string, unknown>) => patch<HorarioTemplate>(`/empresa/horarios/${id}`, body),
    eliminarHorario: (id: string) => del(`/empresa/horarios/${id}`),
    generarBloques: (body: { professional_id?: string; desde: string; hasta: string }) =>
      post<GenerarBloquesResult>('/empresa/horarios/generar', body),
    // bloqueos negativos / horarios especiales (51 · 52.9)
    bloqueos: (professionalId?: string) =>
      get<BloqueoAgenda[]>(`/empresa/bloqueos${professionalId ? `?professional_id=${professionalId}` : ''}`),
    crearBloqueo: (body: { professional_id: string; branch_id?: string | null; inicio: string; fin: string; motivo?: string }) =>
      post<BloqueoAgenda>('/empresa/bloqueos', body),
    eliminarBloqueo: (id: string) => del(`/empresa/bloqueos/${id}`),
    // liquidación de profesionales (58)
    liquidaciones: (period?: string, estado: string = 'activas') => {
      const p = new URLSearchParams({ estado });
      if (period) p.set('period', period);
      return get<LiquidacionProf[]>(`/empresa/liquidaciones?${p.toString()}`);
    },
    liquidacionDetalle: (profId: string, period?: string, estado: string = 'activas') => {
      const p = new URLSearchParams({ estado });
      if (period) p.set('period', period);
      return get<LiquidacionDetalle[]>(`/empresa/liquidaciones/${profId}/detalle?${p.toString()}`);
    },
    finalizarLiquidacion: (profId: string, hasta?: string) =>
      post<{ professional_id: string; profesional_nombre: string; finalizadas: number; monto: number }>(
        `/empresa/liquidaciones/${profId}/finalizar`, hasta ? { hasta } : {},
      ),
    // medios de pago (66)
    mediosPago: () => get<MedioPago[]>('/empresa/medios-pago'),
    crearMedioPago: (body: { nombre: string; retencion_pct?: number; facturable?: boolean; permite_devolucion?: boolean; acepta_cuotas?: boolean }) =>
      post<MedioPago>('/empresa/medios-pago', body),
    editarMedioPago: (id: string, body: Record<string, unknown>) => patch<MedioPago>(`/empresa/medios-pago/${id}`, body),
    eliminarMedioPago: (id: string) => del(`/empresa/medios-pago/${id}`),
    // bancos e Isapres/Fonasa (63)
    entidadesFinancieras: (tipo?: string) => get<EntidadFinanciera[]>(`/empresa/entidades-financieras${tipo ? `?tipo=${tipo}` : ''}`),
    crearEntidad: (body: { nombre: string; tipo: string }) => post<EntidadFinanciera>('/empresa/entidades-financieras', body),
    editarEntidad: (id: string, body: Record<string, unknown>) => patch<EntidadFinanciera>(`/empresa/entidades-financieras/${id}`, body),
    eliminarEntidad: (id: string) => del(`/empresa/entidades-financieras/${id}`),
    // aranceles multi-tabla (62)
    aranceles: () => get<Arancel[]>('/empresa/aranceles'),
    crearArancel: (body: { nombre: string; tipo: string; es_base?: boolean }) => post<Arancel>('/empresa/aranceles', body),
    editarArancel: (id: string, body: Record<string, unknown>) => patch<Arancel>(`/empresa/aranceles/${id}`, body),
    eliminarArancel: (id: string) => del(`/empresa/aranceles/${id}`),
    arancelCategorias: (id: string) => get<ArancelCat[]>(`/empresa/aranceles/${id}/categorias`),
    crearCategoria: (id: string, body: { nombre: string; orden?: number }) => post<ArancelCat>(`/empresa/aranceles/${id}/categorias`, body),
    eliminarCategoria: (cid: string) => del(`/empresa/aranceles/categorias/${cid}`),
    arancelItems: (id: string) => get<ArancelItem[]>(`/empresa/aranceles/${id}/items`),
    crearArancelItem: (id: string, body: Record<string, unknown>) => post<ArancelItem>(`/empresa/aranceles/${id}/items`, body),
    importarArancel: (id: string, contenido: string) => post<{ creados: number; actualizados: number; total_filas: number; errores: { fila: number; motivo: string }[] }>(`/empresa/aranceles/${id}/importar`, { contenido }),
    editarArancelItem: (iid: string, body: Record<string, unknown>) => patch<ArancelItem>(`/empresa/aranceles/items/${iid}`, body),
    eliminarArancelItem: (iid: string) => del(`/empresa/aranceles/items/${iid}`),
    incrementarArancel: (id: string, pct: number) => post<{ afectados: number }>(`/empresa/aranceles/${id}/incrementar`, { pct }),
    copiarArancelBase: (id: string) => post<{ copiados: number }>(`/empresa/aranceles/${id}/copiar-base`, {}),
    motivos: () => get<MotivoAtencion[]>('/empresa/motivos'),
    crearMotivo: (body: { nombre: string; specialty_id?: string }) => post<MotivoAtencion>('/empresa/motivos', body),
    editarMotivo: (id: string, body: { nombre?: string; specialty_id?: string; activo?: boolean }) => patch<MotivoAtencion>(`/empresa/motivos/${id}`, body),
    eliminarMotivo: (id: string) => del(`/empresa/motivos/${id}`),
    recintos: (tipo?: string) => get<Recinto[]>(`/empresa/recintos${tipo ? `?tipo=${tipo}` : ''}`),
    crearRecinto: (body: { nombre: string; numero: number; tipo: string; branch_id?: string }) => post<Recinto>('/empresa/recintos', body),
    eliminarRecinto: (id: string) => del(`/empresa/recintos/${id}`),
    servicios: () => get<ServicioAdmin[]>('/empresa/servicios'),
    crearServicio: (body: { nombre: string; precio: number; duracion_min: number; specialty_id?: string; afecto_iva?: boolean; comisiona?: boolean }) => post<ServicioAdmin>('/empresa/servicios', body),
    editarServicio: (id: string, body: { nombre?: string; precio?: number; duracion_min?: number; activo?: boolean; afecto_iva?: boolean; comisiona?: boolean }) => patch<ServicioAdmin>(`/empresa/servicios/${id}`, body),
    eliminarServicio: (id: string) => del(`/empresa/servicios/${id}`),
    promociones: () => get<Promocion[]>('/empresa/promociones'),
    crearPromo: (body: { nombre: string; descuento?: string; segmento?: string; estado?: string }) => post<Promocion>('/empresa/promociones', body),
    editarPromo: (id: string, body: { estado?: string; nombre?: string; descuento?: string }) => patch<Promocion>(`/empresa/promociones/${id}`, body),
    eliminarPromo: (id: string) => del(`/empresa/promociones/${id}`),
    // Base de conocimiento IA (72)
    conocimiento: () => get<FuenteConocimiento[]>('/empresa/conocimiento'),
    subirTextoConocimiento: (body: { nombre: string; texto: string }) => post<FuenteConocimiento>('/empresa/conocimiento/texto', body),
    subirPdfConocimiento: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return request<FuenteConocimiento>('/empresa/conocimiento/pdf', { method: 'POST', body: form });
    },
    editarFuenteConocimiento: (id: string, body: { nombre?: string; activo?: boolean }) => patch<FuenteConocimiento>(`/empresa/conocimiento/${id}`, body),
    eliminarFuenteConocimiento: (id: string) => del(`/empresa/conocimiento/${id}`),
    buscarConocimiento: (consulta: string, k = 4) => post<{ resultados: FragmentoConocimiento[] }>('/empresa/conocimiento/buscar', { consulta, k }),
    consultarConocimiento: (pregunta: string) => post<ConsultaIA>('/empresa/conocimiento/consultar', { pregunta }),
    info: () => get<InfoEmpresa>('/empresa/info'),
    editarInfo: (body: { razon_social?: string; responsable_sanitario?: string; logo?: string }) => patch<InfoEmpresa>('/empresa/info', body),
    funcionarios: () => get<Funcionario[]>('/empresa/funcionarios'),
    altaFuncionario: (correo: string) => post<Funcionario>('/empresa/funcionarios', { correo }),
    bajaFuncionario: (id: string) => del(`/empresa/funcionarios/${id}`),
    // agenda online pública (60)
    agendaOnline: () => get<AgendaOnlineConfig>('/empresa/agenda-online/config'),
    guardarAgendaOnline: (body: { slug?: string; habilitada?: boolean; anticipacion_horas?: number; ventana_dias?: number; mensaje?: string; requiere_prepago?: boolean; monto_prepago?: number }) => put<AgendaOnlineConfig>('/empresa/agenda-online/config', body),
    agendaOnlineDashboard: (dias = 30) => get<AgendaOnlineDashboard>(`/empresa/agenda-online/dashboard?dias=${dias}`),
    marcarReservable: (serviceId: string, reservable: boolean) => patch<void>(`/empresa/servicios/${serviceId}/reservable`, { reservable_online: reservable }),
    solicitudes: (estado?: string) => get<SolicitudOnline[]>(`/empresa/solicitudes${estado ? `?estado=${estado}` : ''}`),
    confirmarSolicitud: (id: string) => post<SolicitudOnline>(`/empresa/solicitudes/${id}/confirmar`),
    rechazarSolicitud: (id: string) => post<SolicitudOnline>(`/empresa/solicitudes/${id}/rechazar`),
  },
  publica: {
    clinica: (slug: string) => get<ClinicaPublica>(`/public/reservas/${slug}`),
    disponibilidad: (slug: string, serviceId: string) => get<SlotPublico[]>(`/public/reservas/${slug}/disponibilidad?service_id=${serviceId}`),
    reservar: (slug: string, body: ReservaPublicaInput) => post<ReservaPublicaOut>(`/public/reservas/${slug}`, body),
    estado: (slug: string, codigo: string) => get<{ codigo: string; estado: string; inicio: string; fin: string }>(`/public/reservas/${slug}/estado/${codigo}`),
    prepago: (slug: string, codigo: string) => post<PrepagoPublico>(`/public/reservas/${slug}/prepago/${codigo}`),
  },
  cajas: {
    lista: (estado?: string) => get<Caja[]>(`/empresa/cajas${estado ? `?estado=${estado}` : ''}`),
    miCaja: () => get<CajaDetalle | null>('/empresa/cajas/mi-caja'),
    detalle: (id: string) => get<CajaDetalle>(`/empresa/cajas/${id}`),
    abrir: (abono_inicial: number) => post<CajaDetalle>('/empresa/cajas', { abono_inicial }),
    movimiento: (id: string, body: { tipo: string; medio: string; monto: number; patient_id?: string; appointment_id?: string; convenio?: string; referencia?: string; boleta?: string; glosa?: string; emitir_boleta?: boolean; tipo_documento?: string; exento?: boolean; receptor_tax_id?: string; receptor_nombre?: string }) =>
      post<MovimientoCaja>(`/empresa/cajas/${id}/movimientos`, body),
    cerrar: (id: string, fondo_fijo: number) => post<CajaDetalle>(`/empresa/cajas/${id}/cerrar`, { fondo_fijo }),
    gastos: (period?: string) => get<GastosResumen>(`/empresa/cajas/reportes/gastos${period ? `?period=${period}` : ''}`),
    // anulación auditada de pagos (67)
    anularPago: (paymentId: string, motivo?: string) => post<unknown>(`/empresa/cajas/pagos/${paymentId}/anular`, motivo ? { motivo } : {}),
  },
  tributario: {
    tipos: () => get<TributarioTipos>('/tributario/tipos'),
    emisor: () => get<TaxEmisor | null>('/tributario/emisor'),
    guardarEmisor: (body: TaxEmisorInput) => put<TaxEmisor>('/tributario/emisor', body),
    folios: () => get<TaxFolio[]>('/tributario/folios'),
    registrarFolios: (body: { tipo_documento: string; serie?: string; desde: number; hasta: number; caf_ref?: string }) =>
      post<TaxFolio>('/tributario/folios', body),
    documentos: (params?: { estado?: string; tipo_documento?: string }) => {
      const q = new URLSearchParams(Object.entries(params ?? {}).filter(([, v]) => v)).toString();
      return get<TaxDocResumen[]>(`/tributario/documentos${q ? `?${q}` : ''}`);
    },
    emitir: (body: EmitirTributarioInput) => post<TaxDoc>('/tributario/documentos', body),
    documento: (id: string) => get<TaxDoc>(`/tributario/documentos/${id}`),
    estado: (id: string) => get<{ id: string; estado: string; organo: string; track_id: string | null; sello: string | null; motivo: string | null }>(`/tributario/documentos/${id}/estado`),
    anular: (id: string, motivo: string) => post<TaxDoc>(`/tributario/documentos/${id}/anular`, { motivo }),
  },
  admin: {
    inicio: () => get<AdminKpis>('/admin/inicio'),
    clinicas: () => get<ClinicAdmin[]>('/admin/clinicas'),
    altaClinica: (body: { razon_social: string; pais: string; responsable_sanitario?: string; sucursal_nombre: string; admin_nombre: string; admin_correo: string; admin_password: string }) =>
      post<{ clinic_id: string; branch_id: string; admin_user_id: string }>('/admin/clinicas', body),
    bajaClinica: (id: string) => del(`/admin/clinicas/${id}`),
    usuarios: () => get<UsuarioAdmin[]>('/admin/usuarios'),
    crearUsuario: (body: { nombre: string; correo: string; password: string; role: string; clinic_id?: string }) => post<UsuarioAdmin>('/admin/usuarios', body),
    editarUsuario: (userId: string, body: Partial<{ nombre: string; correo: string; telefono: string; password: string; activo: boolean }>) =>
      patch<UsuarioAdmin>(`/admin/usuarios/${userId}`, body),
    permisosCatalogo: () => get<PermisoCatalogo>('/admin/permisos/catalogo'),
    permisosUsuario: (userId: string) => get<PermisoOverride[]>(`/admin/usuarios/${userId}/permisos`),
    setPermisoUsuario: (userId: string, body: { clinic_id: string; resource: string; action: string; allow: boolean }) => put<PermisoOverride>(`/admin/usuarios/${userId}/permisos`, body),
    eliminarPermisoUsuario: (userId: string, overrideId: string) => del(`/admin/usuarios/${userId}/permisos/${overrideId}`),
    // Perfiles de acceso reutilizables (48)
    perfiles: () => get<PerfilAcceso[]>('/admin/perfiles'),
    crearPerfil: (body: { clinic_id: string; nombre: string; base_role: string; permisos: PermisoItem[]; sin_restriccion: boolean }) =>
      post<PerfilAcceso>('/admin/perfiles', body),
    editarPerfil: (id: string, body: Partial<{ nombre: string; permisos: PermisoItem[]; sin_restriccion: boolean; activo: boolean }>) =>
      patch<PerfilAcceso>(`/admin/perfiles/${id}`, body),
    eliminarPerfil: (id: string) => del(`/admin/perfiles/${id}`),
    perfilUsuario: (userId: string) => get<PerfilAsignado[]>(`/admin/usuarios/${userId}/perfil`),
    asignarPerfil: (userId: string, body: { clinic_id: string; profile_id: string }) =>
      put<PerfilAsignado>(`/admin/usuarios/${userId}/perfil`, body),
    quitarPerfil: (userId: string, clinicId: string) => del(`/admin/usuarios/${userId}/perfil/${clinicId}`),
    planes: () => get<PlanAdmin[]>('/admin/planes'),
    crearPlan: (body: { tipo: string; esfera?: string; nombre: string; precio: number }) => post<PlanAdmin>('/admin/planes', body),
    tyc: () => get<TycAdmin[]>('/admin/tyc'),
    publicarTyc: (body: { pais: string; version: string; contenido: string }) => post<TycAdmin>('/admin/tyc', body),
    finanzas: () => get<FinanzasResumen>('/admin/finanzas'),
    ledger: () => get<LedgerEntryAdmin[]>('/admin/finanzas/ledger'),
    auditoria: () => get<AuditEntry[]>('/admin/auditoria'),
    toggleIntegracion: (id: string, activo: boolean) => patch<{ id: string; tipo: string; activo: boolean }>(`/admin/integraciones/${id}`, { activo }),
  },
  crm: {
    consolidado: (period?: string) => get<CrmConsolidado>(`/crm/consolidado${period ? `?period=${period}` : ''}`),
    miClinica: (period?: string) => get<CrmDetalleClinica>(`/crm/mi-clinica${period ? `?period=${period}` : ''}`),
    detalleClinica: (clinicId: string, period?: string) => get<CrmDetalleClinica>(`/crm/clinicas/${clinicId}${period ? `?period=${period}` : ''}`),
    liquidaciones: (period?: string) => get<CrmLiquidacion[]>(`/crm/liquidaciones${period ? `?period=${period}` : ''}`),
    conciliar: (splitId: string) => post<{ split_id: string; estado: string; conciliado_at: string | null }>(`/crm/liquidaciones/${splitId}/conciliar`),
    exportar: (period?: string) => get<CrmAsientoExport[]>(`/crm/exportar${period ? `?period=${period}` : ''}`),
    campanas: (clinicId?: string) => get<CrmCampanas>(`/crm/campanas${clinicId ? `?clinic_id=${clinicId}` : ''}`),
    crearCampana: (body: { clinic_id?: string; nombre: string; canal: string; presupuesto: number; gasto?: number; leads?: number; conversiones?: number }) =>
      post<CrmCampana>('/crm/campanas', body),
    actualizarCampana: (id: string, body: { estado?: string; leads?: number; conversiones?: number; gasto_adicional?: number }) => patch<CrmCampana>(`/crm/campanas/${id}`, body),
    eliminarCampana: (id: string) => del(`/crm/campanas/${id}`),
    atribucion: (id: string) => get<CrmAtribucion>(`/crm/campanas/${id}/atribucion`),
    // Tanda 6 — gestión CRM
    tareas: (estado?: string) => get<Tarea[]>(`/crm/tareas${estado ? `?estado=${estado}` : ''}`),
    crearTarea: (body: { titulo: string; descripcion?: string; vencimiento?: string }) => post<Tarea>('/crm/tareas', body),
    actualizarTarea: (id: string, body: { estado?: string; titulo?: string; descripcion?: string }) => patch<Tarea>(`/crm/tareas/${id}`, body),
    eliminarTarea: (id: string) => del(`/crm/tareas/${id}`),
    encuestas: () => get<Encuesta[]>('/crm/encuestas'),
    encuestasResumen: () => get<EncuestaResumen>('/crm/encuestas/resumen'),
    enviarEncuesta: (body: { paciente_nombre?: string }) => post<Encuesta>('/crm/encuestas', body),
    responderEncuesta: (id: string, score: number, comentario?: string) => post<Encuesta>(`/crm/encuestas/${id}/responder`, { score, comentario }),
    plantillas: () => get<Plantilla[]>('/crm/plantillas'),
    crearPlantilla: (body: { nombre: string; canal: string; asunto?: string; cuerpo: string }) => post<Plantilla>('/crm/plantillas', body),
    eliminarPlantilla: (id: string) => del(`/crm/plantillas/${id}`),
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
  integraciones: {
    estado: () => get<IntegracionesEstado>('/integraciones/estado'),
    whatsapp: (texto: string) => post<AsistenteRespuesta>('/integraciones/whatsapp/mensaje', { texto }),
    mapas: (lat: number, lng: number) => get<SucursalCercana[]>(`/integraciones/mapas/sucursales?lat=${lat}&lng=${lng}`),
  },
  inventario: {
    proveedores: () => get<Proveedor[]>('/empresa/inventario/proveedores'),
    crearProveedor: (body: { nombre: string; rut?: string; contacto?: string }) => post<Proveedor>('/empresa/inventario/proveedores', body),
    editarProveedor: (id: string, body: Partial<{ nombre: string; rut: string; contacto: string; activo: boolean }>) => patch<Proveedor>(`/empresa/inventario/proveedores/${id}`, body),
    eliminarProveedor: (id: string) => del(`/empresa/inventario/proveedores/${id}`),
    centros: () => get<CentroCosto[]>('/empresa/inventario/centros-costo'),
    crearCentro: (body: { nombre: string }) => post<CentroCosto>('/empresa/inventario/centros-costo', body),
    editarCentro: (id: string, body: Partial<{ nombre: string; activo: boolean }>) => patch<CentroCosto>(`/empresa/inventario/centros-costo/${id}`, body),
    eliminarCentro: (id: string) => del(`/empresa/inventario/centros-costo/${id}`),
    bodegas: () => get<Bodega[]>('/empresa/inventario/bodegas'),
    crearBodega: (body: { nombre: string; branch_id?: string }) => post<Bodega>('/empresa/inventario/bodegas', body),
    editarBodega: (id: string, body: Partial<{ nombre: string; branch_id: string; activo: boolean }>) => patch<Bodega>(`/empresa/inventario/bodegas/${id}`, body),
    eliminarBodega: (id: string) => del(`/empresa/inventario/bodegas/${id}`),
    items: () => get<InsumoItem[]>('/empresa/inventario/items'),
    crearItem: (body: { nombre: string; sku?: string; unidad?: string; stock_minimo?: number; supplier_id?: string; cost_center_id?: string }) => post<InsumoItem>('/empresa/inventario/items', body),
    editarItem: (id: string, body: Partial<{ nombre: string; sku: string; unidad: string; stock_minimo: number; supplier_id: string; cost_center_id: string; activo: boolean }>) => patch<InsumoItem>(`/empresa/inventario/items/${id}`, body),
    eliminarItem: (id: string) => del(`/empresa/inventario/items/${id}`),
    entrada: (id: string, body: { warehouse_id: string; cantidad: number; lote?: string; vencimiento?: string; supplier_id?: string; cost_center_id?: string; motivo?: string }) => post<InsumoItem>(`/empresa/inventario/items/${id}/entrada`, body),
    salida: (id: string, body: { warehouse_id: string; cantidad: number; cost_center_id?: string; motivo?: string }) => post<InsumoItem>(`/empresa/inventario/items/${id}/salida`, body),
    ajuste: (id: string, body: { lot_id: string; cantidad_nueva: number; motivo?: string }) => post<InsumoItem>(`/empresa/inventario/items/${id}/ajuste`, body),
    lotes: (id: string) => get<LoteInsumo[]>(`/empresa/inventario/items/${id}/lotes`),
    movimientos: (id: string) => get<MovimientoStock[]>(`/empresa/inventario/items/${id}/movimientos`),
    alertas: () => get<AlertasInventario>('/empresa/inventario/alertas'),
  },
  labs: {
    lista: () => get<LabDental[]>('/empresa/labs'),
    crear: (body: { nombre: string; rut?: string; contacto?: string }) => post<LabDental>('/empresa/labs', body),
    editar: (id: string, body: Partial<{ nombre: string; rut: string; contacto: string; activo: boolean }>) => patch<LabDental>(`/empresa/labs/${id}`, body),
    eliminar: (id: string) => del(`/empresa/labs/${id}`),
    servicios: (labId: string) => get<LabPrestacion[]>(`/empresa/labs/${labId}/servicios`),
    crearServicio: (labId: string, body: { nombre: string; costo: number; precio: number }) => post<LabPrestacion>(`/empresa/labs/${labId}/servicios`, body),
    editarServicio: (sid: string, body: Partial<{ nombre: string; costo: number; precio: number; activo: boolean }>) => patch<LabPrestacion>(`/empresa/labs/servicios/${sid}`, body),
    eliminarServicio: (sid: string) => del(`/empresa/labs/servicios/${sid}`),
    ordenes: (params?: { estado?: string; lab_id?: string }) => {
      const p = new URLSearchParams();
      if (params?.estado) p.set('estado', params.estado);
      if (params?.lab_id) p.set('lab_id', params.lab_id);
      const qs = p.toString();
      return get<LabOrden[]>(`/empresa/labs/ordenes${qs ? `?${qs}` : ''}`);
    },
    crearOrden: (body: { lab_id: string; descripcion: string; lab_service_id?: string; patient_id?: string; treatment_plan_id?: string; pieza?: string; costo?: number; precio?: number; fecha_entrega?: string; notas?: string }) => post<LabOrden>('/empresa/labs/ordenes', body),
    cambiarEstadoOrden: (id: string, estado: string) => patch<LabOrden>(`/empresa/labs/ordenes/${id}/estado`, { estado }),
    pagarOrden: (id: string) => post<LabOrden>(`/empresa/labs/ordenes/${id}/pagar`),
    cuentasPorPagar: () => get<CuentaPorPagar[]>('/empresa/labs/cuentas-por-pagar'),
  },
  reportes: {
    biblioteca: () => get<ReporteBib[]>('/empresa/reportes'),
    agendaKpis: (dias = 30) => get<AgendaKpis>(`/empresa/reportes/agenda-kpis?dias=${dias}`),
    // descarga el CSV autenticado y devuelve el blob para que el navegador lo guarde
    exportar: async (id: string, dias = 30): Promise<Blob> => {
      const token = getToken();
      const res = await fetch(`${API_BASE}/empresa/reportes/${id}/export?dias=${dias}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new ApiError(res.status, 'No se pudo exportar');
      return res.blob();
    },
  },
  ia: {
    sugerencias: (estado?: string) => get<SugerenciaIA[]>(`/ia/sugerencias${estado ? `?estado=${estado}` : ''}`),
    aplicar: (id: string) => post<{ aplicada: boolean; ficha: Record<string, unknown>; proximo_control: string | null }>(`/ia/sugerencias/${id}/aplicar`),
    descartar: (id: string) => post<SugerenciaIA>(`/ia/sugerencias/${id}/descartar`),
    recordatorios: () => get<RecordatorioIA[]>('/ia/recordatorios'),
    chat: (texto: string) => post<ChatIA>('/ia/chat', { texto }),
    consultar: (pregunta: string) => post<ConsultaIA>('/ia/consultar', { pregunta }),
    agendar: (serviceId: string) => post<AgendarIA>('/ia/agendar', { service_id: serviceId }),
  },
};

export type { Dependent };
