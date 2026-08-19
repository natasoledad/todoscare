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
  specialty_id?: string | null;
  specialty_nombre?: string | null;
  tipo_especialidad?: string | null; // medica | dental
  duracion_min?: number | null;
  modalidad?: string; // presencial | videoconsulta | ambas
  comision_pct?: number | null; // 0–1
  activo?: boolean;
}

export interface Especialidad {
  id: string;
  nombre: string;
  tipo: string; // medica | dental
  icono: string | null;
  activo: boolean;
}

export interface MotivoAtencion {
  id: string;
  nombre: string;
  specialty_id: string | null;
  specialty_nombre: string | null;
  activo: boolean;
}

export interface HorarioTemplate {
  id: string;
  professional_id: string;
  professional_nombre: string;
  branch_id: string;
  branch_nombre: string;
  room_id: string | null;
  room_nombre: string | null;
  dia_semana: number; // 0=lunes … 6=domingo
  hora_inicio: string; // "HH:MM(:SS)"
  hora_fin: string;
  descanso_inicio: string | null;
  descanso_fin: string | null;
  modalidad: string;
  capacidad: number;
  activo: boolean;
}

export interface GenerarBloquesResult {
  generados: number;
  omitidos: number;
  dias: number;
}

export interface BloqueoAgenda {
  id: string;
  professional_id: string;
  professional_nombre: string;
  branch_id: string | null;
  branch_nombre: string | null;
  inicio: string;
  fin: string;
  motivo: string | null;
  creado_por: string | null;
}

export interface LiquidacionProf {
  professional_id: string;
  nombre: string;
  cantidad: number;
  realizado: number;
  a_pagar: number;
}

export interface LiquidacionDetalle {
  split_id: string;
  fecha: string;
  prestacion: string | null;
  paciente: string | null;
  base: number;
  monto: number;
  estado: string;
}

export interface MedioPago {
  id: string;
  nombre: string;
  retencion_pct: number; // 0–1
  facturable: boolean;
  permite_devolucion: boolean;
  acepta_cuotas: boolean;
  activo: boolean;
}

export interface EntidadFinanciera {
  id: string;
  nombre: string;
  tipo: string; // banco | isapre
  activo: boolean;
}

export interface GastoLinea {
  id: string;
  fecha: string;
  medio: string;
  monto: number;
  glosa: string | null;
  caja_responsable: string | null;
}

export interface GastosResumen {
  periodo: string;
  total: number;
  cantidad: number;
  gastos: GastoLinea[];
}

export interface Arancel {
  id: string;
  nombre: string;
  tipo: string; // base | particular | empresa
  es_base: boolean;
  activo: boolean;
  n_items: number;
}

export interface ArancelCat {
  id: string;
  arancel_id: string;
  nombre: string;
  orden: number;
}

export interface ArancelItem {
  id: string;
  arancel_id: string;
  categoria_id: string | null;
  categoria_nombre: string | null;
  codigo: string | null;
  nombre: string;
  precio: number;
  precio_referencia: number | null;
  permite_descuento: boolean;
  comisiona: boolean;
  activo: boolean;
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
  room_id: string | null;
  room_nombre: string | null;
  reglas: Record<string, unknown> | null;
}

export interface Recinto {
  id: string;
  nombre: string;
  numero: number;
  tipo: string; // medica | dental
  activo: boolean;
  branch_id: string | null;
}

// ---- laboratorios dentales (57) ----
export interface LabDental {
  id: string;
  nombre: string;
  rut: string | null;
  contacto: string | null;
  activo: boolean;
}
export interface LabPrestacion {
  id: string;
  lab_id: string;
  nombre: string;
  costo: number;
  precio: number;
  margen: number;
  activo: boolean;
}

export interface LabOrden {
  id: string;
  lab_id: string;
  lab_nombre: string | null;
  descripcion: string;
  pieza: string | null;
  costo: number;
  precio: number;
  estado: string; // solicitado | en_proceso | en_revision | terminado | cancelado
  fecha_entrega: string | null;
  pagado: boolean;
  patient_id: string | null;
  paciente_nombre: string | null;
  treatment_plan_id: string | null;
  notas: string | null;
  creada: string;
}
export interface CuentaPorPagar {
  lab_id: string;
  lab_nombre: string;
  cantidad_ordenes: number;
  total: number;
}

// ---- inventario (56) ----
export interface Proveedor {
  id: string;
  nombre: string;
  rut: string | null;
  contacto: string | null;
  activo: boolean;
}
export interface CentroCosto {
  id: string;
  nombre: string;
  activo: boolean;
}
export interface Bodega {
  id: string;
  nombre: string;
  branch_id: string | null;
  branch_nombre: string | null;
  activo: boolean;
}
export interface InsumoItem {
  id: string;
  nombre: string;
  sku: string | null;
  unidad: string;
  stock_minimo: number;
  stock_actual: number;
  estado: string; // ok | bajo | sin_stock
  supplier_id: string | null;
  supplier_nombre: string | null;
  cost_center_id: string | null;
  cost_center_nombre: string | null;
  activo: boolean;
}
export interface LoteInsumo {
  id: string;
  warehouse_id: string;
  warehouse_nombre: string | null;
  item_id: string;
  item_nombre: string | null;
  lote: string | null;
  vencimiento: string | null;
  cantidad: number;
  estado: string; // vigente | por_vencer | vencido | sin_vencimiento
}
export interface MovimientoStock {
  id: string;
  tipo: string; // entrada | salida | ajuste
  cantidad: number;
  saldo: number;
  warehouse_nombre: string | null;
  motivo: string | null;
  cost_center_nombre: string | null;
  supplier_nombre: string | null;
  fecha: string;
}
export interface AlertasInventario {
  bajo_minimo: InsumoItem[];
  lotes_por_vencer: LoteInsumo[];
  lotes_vencidos: LoteInsumo[];
}

export interface ServicioAdmin {
  id: string;
  nombre: string;
  precio: number;
  duracion_min: number | null;
  activo: boolean;
  specialty_nombre: string | null;
  afecto_iva: boolean;
  comisiona: boolean;
  reservable_online: boolean;
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

/** Promoción vigente que ve el paciente en su Inicio (solo lectura). */
export interface PromocionPaciente {
  id: string;
  nombre: string;
  descuento: string | null;
  segmento: string | null;
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

// ---- agenda online pública (60) ----
export interface ServicioPublico {
  id: string;
  nombre: string;
  especialidad: string | null;
  icono: string | null;
  precio: number;
  duracion_min: number;
}
export interface SucursalPublica {
  id: string;
  nombre: string;
  direccion: string | null;
}
export interface ClinicaPublica {
  slug: string;
  nombre: string;
  habilitada: boolean;
  mensaje: string | null;
  servicios: ServicioPublico[];
  sucursales: SucursalPublica[];
}
export interface SlotPublico {
  professional_id: string;
  profesional_nombre: string;
  inicio: string;
  fin: string;
}
export interface ReservaPublicaInput {
  service_id: string;
  professional_id: string;
  inicio: string;
  fin: string;
  nombre: string;
  rut?: string;
  telefono?: string;
  email?: string;
  notas?: string;
}
export interface ReservaPublicaOut {
  codigo: string;
  estado: string;
  inicio: string;
  fin: string;
  servicio_nombre: string | null;
  profesional_nombre: string;
}
export interface AgendaOnlineConfig {
  slug: string | null;
  habilitada: boolean;
  anticipacion_horas: number;
  ventana_dias: number;
  mensaje: string | null;
  reservable_url: string | null;
}
export interface AgendaOnlineDashboard {
  dias: number;
  visitas: number;
  solicitudes: number;
  confirmadas: number;
  pendientes: number;
  rechazadas: number;
  tasa_conversion: number;
  tasa_confirmacion: number;
}
export interface SolicitudOnline {
  id: string;
  codigo: string;
  estado: string;
  paciente_nombre: string;
  paciente_rut: string | null;
  paciente_telefono: string | null;
  paciente_email: string | null;
  servicio_nombre: string | null;
  profesional_nombre: string;
  inicio: string;
  fin: string;
  notas: string | null;
  creada: string;
  appointment_id: string | null;
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

// ---- Agenda de la clínica (vista gerencia) ----
export interface CitaAgenda {
  id: string;
  inicio: string;
  fin: string;
  paciente_id: string;
  paciente_nombre: string;
  profesional_id: string;
  profesional_nombre: string;
  servicio_nombre: string | null;
  estado: string;
  monto: number | null;
  facturado: boolean;
}
export interface AgendaDia {
  fecha: string;
  total: number;
  por_estado: Record<string, number>;
  citas: CitaAgenda[];
}

// ---- Cajas (Módulo de arqueo diario) ----
export interface MovimientoCaja {
  id: string;
  tipo: string;        // pago | gasto
  medio: string;
  monto: number;
  convenio: string | null;
  referencia: string | null;
  boleta: string | null;
  glosa: string | null;
  paciente_nombre: string | null;
  appointment_id: string | null;
  fecha: string;
}
export interface Caja {
  id: string;
  responsable_id: string;
  responsable_nombre: string;
  estado: string;      // abierta | cerrada
  abono_inicial: number;
  fondo_fijo: number | null;
  abierta_at: string;
  cerrada_at: string | null;
  recaudado: number;
  gastos: number;
  total: number;
}
export interface CajaDetalle extends Caja {
  por_medio: Record<string, number>;
  transacciones: MovimientoCaja[];
}

// ---- Tanda 3: signos vitales + planes de tratamiento ----
export interface SignosVitales {
  id: string;
  fecha: string;
  appointment_id: string | null;
  presion_sistolica: number | null;
  presion_diastolica: number | null;
  fc_ppm: number | null;
  fr_rpm: number | null;
  spo2: number | null;
  glicemia: number | null;
  eva: number | null;
  peso_kg: number | null;
  talla_cm: number | null;
  temperatura: number | null;
  notas: string | null;
}
export interface PlanItem {
  id: string;
  descripcion: string;
  pieza: string | null;
  cantidad: number;
  precio_unit: number;
  service_id: string | null;
  estado: string;
  subtotal: number;
}
export interface PlanResumen {
  total_bruto: number;
  descuento_pct: number;
  descuento: number;
  total_neto: number;
  realizado: number;
  abonado: number;
  saldo: number;
  progreso_pct: number;
}
export interface PlanTratamiento {
  id: string;
  titulo: string;
  estado: string;
  notas: string | null;
  total: number;
  descuento_pct: number;
  items: PlanItem[];
  resumen: PlanResumen;
  fecha: string;
}

// ---- diferenciadores IA (72) ----
export interface SugerenciaIA {
  id: string;
  resumen: string;
  hallazgos: Record<string, unknown>;
  proximo_control: string | null;
  estado: string;
  examen_nombre: string | null;
  fecha: string;
}
export interface RecordatorioIA {
  tipo: string;
  titulo: string;
  fecha: string | null;
  mensaje: string;
}
export interface ChatIA {
  intent: string;
  reply: string;
  accion: string | null;
}
export interface AgendarIA {
  agendada: boolean;
  appointment_id: string | null;
  servicio_nombre: string | null;
  inicio: string | null;
  fin: string | null;
  mensaje: string;
}

// ---- timeline clínico unificado (70.1) ----
export interface TimelineEvento {
  tipo: string;
  fecha: string;
  titulo: string;
  resumen: string | null;
  icono: string;
  estado: string | null;
}

// ---- Tanda 4: pacientes con deuda + panel de desempeño ----
export interface PacienteLista {
  id: string;
  nombre: string;
  rut: string;
  activo: boolean;
  n_tratamientos: number;
  deuda: number;
}
export interface DesempenoProfesional {
  nombre: string;
  atenciones: number;
  ventas: number;
  a_pagar: number;
  pct: number | null;
}
export interface DesempenoGrupo {
  grupo: string;
  cantidad: number;
  monto: number;
  ticket_medio: number;
}
export interface Desempeno {
  periodo: string;
  ventas: number;
  recaudado: number;
  atenciones: number;
  ticket_medio: number;
  por_profesional: DesempenoProfesional[];
  por_grupo: DesempenoGrupo[];
}

// ---- Tanda 5: documentos clínicos + periodontograma ----
export interface DocumentoClinico {
  id: string;
  tipo: string;
  titulo: string;
  contenido: string | null;
  estado: string;
  fecha: string;
}
export interface Periodontograma {
  id: string;
  datos: Record<string, { ps?: number; sangrado?: boolean }>;
  notas: string | null;
  fecha: string;
  tomas_anteriores: number;
}

// ---- Tanda 6: gestión CRM ----
export interface Tarea {
  id: string;
  titulo: string;
  descripcion: string | null;
  patient_id: string | null;
  estado: string;
  vencimiento: string | null;
  fecha: string;
}
export interface Encuesta {
  id: string;
  paciente_nombre: string | null;
  estado: string;
  score: number | null;
  comentario: string | null;
  fecha: string;
  respondida_at: string | null;
}
export interface EncuestaResumen {
  enviadas: number;
  respondidas: number;
  tasa_respuesta: number;
  promedio: number | null;
  nps: number | null;
}
export interface Plantilla {
  id: string;
  nombre: string;
  canal: string;
  asunto: string | null;
  cuerpo: string;
}

// ── Tanda 7: documentos tributarios electrónicos (SII Chile / Nota Fiscal Brasil) ──
export interface TributarioTipos {
  pais: string | null;
  tipos: string[];
  habilitado: boolean;
}
export interface TaxEmisor {
  id: string;
  pais: string;
  tax_id: string;
  razon_social: string;
  giro: string | null;
  direccion: string | null;
  config: Record<string, unknown> | null;
}
export interface TaxEmisorInput {
  tax_id: string;
  razon_social: string;
  giro?: string;
  direccion?: string;
  config?: Record<string, unknown>;
}
export interface TaxFolio {
  id: string;
  tipo_documento: string;
  serie: string | null;
  desde: number;
  hasta: number;
  siguiente: number;
  disponibles: number;
  caf_ref: string | null;
  activo: boolean;
}
export interface TaxDocResumen {
  id: string;
  pais: string;
  jurisdiccion: string;
  organo: string;
  tipo_documento: string;
  codigo: string | null;
  serie: string | null;
  folio: number;
  receptor_nombre: string | null;
  neto: number;
  impuesto: number;
  total: number;
  moneda: string;
  estado: string;
  track_id: string | null;
  emitido_at: string;
}
export interface TaxDoc extends TaxDocResumen {
  receptor_tax_id: string | null;
  exento: number;
  impuesto_detalle: Record<string, unknown> | null;
  items: Array<Record<string, unknown>> | null;
  sello: string | null;
  motivo: string | null;
  referencia_id: string | null;
  xml: string | null;
}
export interface EmitirTributarioInput {
  tipo_documento: string;
  items: Array<{ descripcion: string; cantidad: number; precio_unitario: number; exento?: boolean }>;
  receptor?: { tax_id?: string; nombre?: string };
  serie?: string;
}
