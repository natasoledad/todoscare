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
