/** Catálogo único de estados de una cita, compartido por los portales de
 *  empresa/gerencia y del médico. Una sola fuente de verdad para etiqueta y
 *  color: si cambia un estado o su tono, cambia en los tres roles a la vez.
 *  'completada' la fija el cierre del médico; el resto los mueve recepción. */
export type EstadoCita =
  | 'confirmada'
  | 'en_sala_espera'
  | 'en_atencion'
  | 'completada'
  | 'no_show'
  | 'cancelada';

type EstadoMeta = {
  label: string;
  dot: string;
  chip: string;
  tone: 'teal' | 'warn' | 'danger' | 'muted';
};

export const ESTADOS_CITA: Record<string, EstadoMeta> = {
  confirmada:     { label: 'Confirmada',  dot: 'bg-teal',      chip: 'bg-teal-soft text-teal-dark', tone: 'warn' },
  en_sala_espera: { label: 'En sala',     dot: 'bg-[#B98900]', chip: 'bg-warn-bg text-warn',        tone: 'warn' },
  en_atencion:    { label: 'En atención', dot: 'bg-[#2B6CB0]', chip: 'bg-[#E6EFF7] text-[#2B6CB0]', tone: 'warn' },
  completada:     { label: 'Atendida',    dot: 'bg-[#0B7A66]', chip: 'bg-[#DFF3EC] text-teal-dark', tone: 'teal' },
  no_show:        { label: 'Faltó',       dot: 'bg-[#C86B5E]', chip: 'bg-[#F7E7E4] text-danger',    tone: 'danger' },
  cancelada:      { label: 'Anulada',     dot: 'bg-sub',       chip: 'bg-[#EEF2F1] text-sub',       tone: 'muted' },
};

/** Metadatos de un estado, tolerante a valores desconocidos. */
export const estadoCita = (e: string): EstadoMeta =>
  ESTADOS_CITA[e] ?? { label: e, dot: 'bg-sub', chip: 'bg-[#EEF2F1] text-sub', tone: 'muted' };

/** Formato de dinero chileno: $1.234.567 (CLP, sin decimales). */
export const money = (n: number | null | undefined) =>
  n == null ? '—' : `$${Math.round(n).toLocaleString('es-CL')}`;

/** Hora local HH:MM en formato chileno. */
export const hhmm = (iso: string) =>
  new Date(iso).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
