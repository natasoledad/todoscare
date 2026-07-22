import type {
  AuthOut,
  Cierre,
  Cita,
  CitaMedico,
  ClinicPublic,
  Dependent,
  EmergencyQr,
  Examen,
  FichaPaciente,
  FichaUpdateInput,
  Hospitalizacion,
  Liquidacion,
  Me,
  Medicamento,
  Movimiento,
  Odontograma,
  OnboardingInput,
  Orden,
  PatientMe,
  PrescripcionResult,
  Prontuario,
  QrAccessLog,
  RegisterInput,
  ReservaInput,
  Servicio,
  Slot,
  TycVersion,
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
};

export type { Dependent };
