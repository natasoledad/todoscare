export interface ClinicPublic {
  id: string;
  razon_social: string;
  pais: string;
}

export interface Me {
  user_id: string;
  nombre: string;
  email: string;
  roles: string[];
  grants: { role: string; clinic_id: string | null; branch_id: string | null }[];
}

// ---- médico ----
export interface CitaMedico {
  id: string;
  patient_id: string;
  paciente_nombre: string;
  servicio_nombre: string;
  inicio: string;
  fin: string;
  estado: string;
  atendida: boolean;
}

export interface ExamenFicha {
  nombre: string;
  fecha: string;
  estado: string;
}

export interface HospitalizacionFicha {
  motivo: string;
  centro: string | null;
  ingreso: string | null;
}

export interface FichaPaciente {
  patient_id: string;
  nombre: string;
  rut: string;
  nivel: string;
  ficha: Record<string, unknown>;
  examenes: ExamenFicha[];
  hospitalizaciones: HospitalizacionFicha[];
  odontograma: Record<string, { estado: string }>;
}

export interface Prontuario {
  id: string;
  contenido: Record<string, unknown> & { enmiendas?: { nota: string; fecha: string }[] };
  creado: string;
}

export interface AlertaClinica {
  tipo: string;
  medicamento: string;
  detalle: string;
}

export interface PrescripcionMedico {
  id: string;
  items: { medicamento: string; cantidad?: string; indicaciones?: string }[];
  estado: string;
  firmado_en: string | null;
}

export interface PrescripcionResult {
  prescripcion: PrescripcionMedico | null;
  alertas: AlertaClinica[];
}

export interface Orden {
  id: string;
  tipo: string;
  estado: string;
  creada: string;
}

export interface Cierre {
  cita_id: string;
  estado: string;
  split_monto: number | null;
}

export interface Liquidacion {
  fecha: string;
  monto: number;
  base: number | null;
  ref: string | null;
}

// ---- empresa ----
export interface EmpresaKpis {
  clinic_nombre: string;
  citas_hoy: number;
  ingresos_mes: number;
  servicios_activos: number;
  promos_activas: number;
  mas_vendidos: { nombre: string; cantidad: number }[];
}

export interface Profesional {
  id: string;
  nombre: string;
}

export interface Branch {
  id: string;
  nombre: string;
}

export interface Bloque {
  id: string;
  professional_id: string;
  professional_nombre: string;
  branch_nombre: string;
  inicio: string;
  fin: string;
  reglas: Record<string, unknown> | null;
}

export interface ServicioAdmin {
  id: string;
  nombre: string;
  precio: number;
  duracion_min: number | null;
  activo: boolean;
  specialty_nombre: string | null;
}

export interface Promocion {
  id: string;
  nombre: string;
  descuento: string | null;
  vigencia_inicio: string | null;
  vigencia_fin: string | null;
  segmento: string | null;
  estado: 'Activa' | 'Borrador';
}

export interface InfoEmpresa {
  clinic_id: string;
  razon_social: string;
  responsable_sanitario: string | null;
  pais: string;
  sucursales: Branch[];
}

export interface Funcionario {
  id: string;
  nombre: string;
  correo: string;
  estado: string;
}

// ---- admin ----
export interface AdminKpis {
  alcance: 'plataforma' | 'clínica';
  clinicas: number;
  pacientes: number;
  citas_hoy: number;
  ingresos_mes: number;
}

export interface ClinicAdmin {
  id: string;
  razon_social: string;
  responsable_sanitario: string | null;
  pais: string;
  activo: boolean;
  sucursales: number;
  pacientes: number;
}

export interface RoleAssignmentAdmin {
  id: string;
  role: string;
  clinic_id: string | null;
  branch_id: string | null;
}

export interface UsuarioAdmin {
  id: string;
  nombre: string;
  email: string;
  activo: boolean;
  roles: RoleAssignmentAdmin[];
}

export interface PlanAdmin {
  id: string;
  tipo: string;
  esfera: string | null;
  nombre: string;
  precio: number;
}

export interface TycAdmin {
  id: string;
  pais: string;
  version: string;
  publicado_en: string;
}

export interface FinanzasResumen {
  ingresos_mes: number;
  split_profesionales: number;
  cashback_emitido: number;
}

export interface LedgerEntryAdmin {
  fecha: string;
  tipo: string;
  monto: number;
  moneda: string;
  ref: string | null;
}

export interface AuditEntry {
  fecha: string;
  actor: string | null;
  accion: string;
  recurso: string;
  clinic_id: string | null;
}

export interface TycVersion {
  id: string;
  pais: string;
  version: string;
  contenido: string;
  publicado_en: string;
}

export interface RegisterInput {
  nombre: string;
  rut: string;
  telefono: string;
  direccion: string;
  correo: string;
  password: string;
  clinic_id: string;
  tyc_version_id: string;
}

export interface AuthOut {
  access_token: string;
  token_type: string;
}

export interface Dependent {
  id: string;
  nombre: string;
}

export interface Wallet {
  puntos: number;
  cashback: number;
}

export interface PatientMe {
  id: string;
  nombre: string;
  correo: string;
  telefono: string;
  direccion: string;
  rut: string;
  nivel: 'Bronce' | 'Plata' | 'Oro' | 'Diamante';
  onboarding_completado: boolean;
  wallet: Wallet;
  dependents: Dependent[];
  ficha: Record<string, unknown>;
}

export interface OnboardingAnswers {
  motivo?: string | null;
  condicion?: string | null;
  actividad?: string | null;
  alergias?: string | null;
  seguro?: string | null;
}

export interface OnboardingInput {
  answers: OnboardingAnswers;
  dependents: { nombre: string }[];
}

export interface FichaUpdateInput {
  fecha_nacimiento?: string;
  sexo?: string;
  contacto_emergencia?: string;
  grupo_sanguineo?: string;
  alergias?: string;
  medicacion_actual?: string;
  antecedentes?: string;
  seguro?: string;
}

export interface Servicio {
  id: string;
  nombre: string;
  icono: string | null;
  precio: number;
  duracion_min: number;
}

export interface Slot {
  professional_id: string;
  inicio: string;
  fin: string;
}

export interface ReservaInput {
  service_id: string;
  professional_id: string;
  inicio: string;
  fin: string;
}

export interface Cita {
  id: string;
  servicio_nombre: string;
  inicio: string;
  fin: string;
  estado: 'confirmada' | 'completada' | 'cancelada' | 'no_show';
  ubicacion: string;
}

export interface Examen {
  id: string;
  nombre: string;
  fecha: string;
  estado: string;
  archivo_url: string | null;
}

export interface Odontograma {
  piezas: Record<string, { estado: string }>;
}

export interface Hospitalizacion {
  id: string;
  motivo: string;
  centro: string | null;
  ingreso: string | null;
  egreso: string | null;
}

export interface EmergencyQr {
  token: string;
  resumen: { grupo_sanguineo?: string | null; alergias?: string | null };
  activo: boolean;
}

export interface QrAccessLog {
  fecha: string;
  profesional_nombre: string | null;
}

export interface Medicamento {
  nombre: string;
  cantidad: string;
  indicaciones: string | null;
  precio: number | null;
}

export interface Movimiento {
  tipo: string;
  fecha: string;
  puntos: number | null;
  cashback: number | null;
  motivo: string | null;
}

// ── CRM (Fase 6) ──
export interface CrmClinicaRow {
  clinic_id: string;
  razon_social: string;
  pais: string;
  ingresos: number;
  margen: number | null;
  variacion: number | null;
  pacientes: number;
}

export interface CrmConsolidado {
  alcance: string;
  period: string;
  ingresos_totales: number;
  variacion: number | null;
  n_clinicas: number;
  n_pacientes: number;
  clinicas: CrmClinicaRow[];
}

export interface CrmIngresoServicio {
  servicio: string;
  monto: number;
}

export interface CrmMarketing {
  gasto_marketing: number;
  nuevos_pacientes: number;
  cac: number | null;
  ltv: number | null;
  ltv_cac_ratio: number | null;
  roas: number | null;
}

export interface CrmCampana {
  id: string;
  clinic_id: string;
  nombre: string;
  canal: string;
  estado: 'activa' | 'pausada' | 'finalizada';
  presupuesto: number;
  gasto: number;
  leads: number;
  conversiones: number;
  conversiones_reales: number;
  fecha_inicio: string | null;
  fecha_fin: string | null;
  cpl: number | null;
  cac: number | null;
  cac_real: number | null;
  conversion_rate: number | null;
  presupuesto_usado: number | null;
}

export interface CrmCampanasResumen {
  campanas: number;
  activas: number;
  inversion: number;
  gasto: number;
  leads: number;
  conversiones: number;
  conversiones_reales: number;
  cac_promedio: number | null;
  cac_real_promedio: number | null;
  conversion_rate: number | null;
}

export interface CrmAtribucion {
  campaign_id: string;
  nombre: string;
  canal: string;
  gasto: number;
  leads: number;
  conversiones_meta: number;
  conversiones_reales: number;
  ingresos_atribuidos: number;
  cac_real: number | null;
  roi_real: number | null;
  roas_real: number | null;
  pacientes: string[];
}

export interface CrmCampanas {
  resumen: CrmCampanasResumen;
  items: CrmCampana[];
}

export interface CrmDetalleClinica {
  clinic_id: string;
  razon_social: string;
  pais: string;
  period: string;
  ingresos: number;
  variacion: number | null;
  margen: number | null;
  ticket_promedio: number;
  n_atenciones: number;
  cuentas_por_cobrar: number;
  ocupacion: number;
  por_liquidar: number;
  marketing: CrmMarketing;
  ingresos_por_servicio: CrmIngresoServicio[];
}

export interface CrmLiquidacion {
  split_id: string;
  clinic_id: string;
  razon_social: string;
  prestador: string;
  monto: number;
  fecha: string;
  estado: string;
}

export interface CrmAsientoExport {
  fecha: string;
  clinica: string;
  tipo: string;
  monto: number;
  moneda: string;
  ref: string | null;
}

// ── Aseguradora / Prestador (Fase 7) ──
export interface AseguradoraKpis {
  insurer_nombre: string;
  tipo: string;
  afiliados: number;
  autorizaciones_pendientes: number;
  atenciones_mes: number;
  por_liquidar: number;
}

export interface Convenio {
  agreement_id: string;
  clinic_id: string;
  clinica: string;
  vigencia_inicio: string | null;
  vigencia_fin: string | null;
  vigente: boolean;
  aranceles: number;
}

export interface Arancel {
  arancel_id: string;
  service_id: string;
  servicio: string;
  cobertura_pct: number;
  copago: number;
}

export interface Afiliado {
  affiliate_id: string;
  patient_id: string | null;
  nombre: string | null;
  documento_identidad: string;
  plan_cobertura: string | null;
  vigencia_desde: string | null;
  vigencia_hasta: string | null;
  vigente: boolean;
}

export interface Autorizacion {
  authorization_id: string;
  agreement_id: string;
  patient_id: string;
  paciente: string;
  servicio: string;
  clinica: string;
  estado: string;
  motivo_rechazo: string | null;
  resuelto_en: string | null;
  fecha: string;
}

export interface LiquidacionAseg {
  settlement_id: string;
  agreement_id: string;
  clinica: string;
  periodo: string;
  monto: number;
  estado: string;
  pagado_at: string | null;
}

export interface RedClinica {
  clinic_id: string;
  clinica: string;
  pais: string;
  vigente: boolean;
}

export interface FichaAfiliado {
  patient_id: string;
  nombre: string;
  documento_identidad: string | null;
  plan_cobertura: string | null;
  prestaciones_autorizadas: { servicio: string; diagnostico: string | null }[];
}

// ── Integraciones (Fase 8) ──
export interface AsistenteRespuesta {
  intent: string;
  reply: string;
}

export interface ConectorEstado {
  id: string;
  tipo: string;
  activo: boolean;
}

export interface IntegracionEvento {
  tipo: string;
  direccion: string;
  estado: string;
  ref: string | null;
  resultado: Record<string, unknown> | null;
  fecha: string;
}

export interface IntegracionesEstado {
  conectores: ConectorEstado[];
  eventos_recientes: IntegracionEvento[];
}

export interface SucursalCercana {
  branch_id: string;
  clinic_id: string;
  nombre: string;
  direccion: string | null;
  geo: { lat: number; lng: number } | null;
  distancia_km: number | null;
}
