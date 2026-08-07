import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import type { AgendaDia, CitaAgenda, Profesional } from '../../api/types';

/** Estados operativos de una cita, con etiqueta y color (leyenda tipo tablero
 *  de gerencia). 'completada' se fija en el cierre del médico, no aquí. */
const ESTADOS: Record<string, { label: string; dot: string; chip: string }> = {
  confirmada:     { label: 'Confirmada',     dot: 'bg-teal',       chip: 'bg-teal-soft text-teal-dark' },
  en_sala_espera: { label: 'En sala',        dot: 'bg-[#B98900]',  chip: 'bg-warn-bg text-warn' },
  en_atencion:    { label: 'En atención',    dot: 'bg-[#2B6CB0]',  chip: 'bg-[#E6EFF7] text-[#2B6CB0]' },
  completada:     { label: 'Atendida',       dot: 'bg-[#0B7A66]',  chip: 'bg-[#DFF3EC] text-teal-dark' },
  no_show:        { label: 'Faltó',          dot: 'bg-[#C86B5E]',  chip: 'bg-[#F7E7E4] text-danger' },
  cancelada:      { label: 'Anulada',        dot: 'bg-sub',        chip: 'bg-[#EEF2F1] text-sub' },
};
const estadoMeta = (e: string) => ESTADOS[e] ?? { label: e, dot: 'bg-sub', chip: 'bg-[#EEF2F1] text-sub' };
// Transiciones que puede hacer recepción/gerencia (no 'completada').
const ACCIONES: { estado: string; label: string }[] = [
  { estado: 'confirmada', label: 'Confirmada' },
  { estado: 'en_sala_espera', label: 'Marcar en sala' },
  { estado: 'en_atencion', label: 'Marcar en atención' },
  { estado: 'no_show', label: 'Marcar falta' },
  { estado: 'cancelada', label: 'Anular cita' },
];

const money = (n: number | null) => (n == null ? '—' : `$${n.toLocaleString('es-CL')}`);
const hhmm = (iso: string) => new Date(iso).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
const iso = (d: Date) => d.toISOString().slice(0, 10);

export function AgendaClinica() {
  const navigate = useNavigate();
  const [fecha, setFecha] = useState(iso(new Date()));
  const [profesionales, setProfesionales] = useState<Profesional[]>([]);
  const [profId, setProfId] = useState('');
  const [data, setData] = useState<AgendaDia | null>(null);
  const [sel, setSel] = useState<CitaAgenda | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.empresa.agenda(fecha, profId || undefined).then(setData);
  useEffect(() => { load(); }, [fecha, profId]);
  useEffect(() => { api.empresa.profesionales().then(setProfesionales); }, []);

  const cambiar = async (id: string, estado: string) => {
    setError(null);
    try {
      await api.empresa.cambiarEstadoCita(id, estado);
      setSel(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo cambiar el estado');
    }
  };

  const shiftDay = (delta: number) => {
    const d = new Date(fecha + 'T12:00:00');
    d.setDate(d.getDate() + delta);
    setFecha(iso(d));
  };

  const resumen = useMemo(() => data?.por_estado ?? {}, [data]);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Agenda de la clínica" onBack={() => navigate('/empresa')} />

      {/* Navegador de fecha */}
      <div className="px-5 pt-3 flex items-center gap-2">
        <button onClick={() => shiftDay(-1)} className="w-9 h-9 rounded-xl border border-border bg-white text-ink">‹</button>
        <input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal"
        />
        <button onClick={() => shiftDay(1)} className="w-9 h-9 rounded-xl border border-border bg-white text-ink">›</button>
      </div>

      {/* Filtro por profesional */}
      <div className="px-5 pt-2">
        <select
          value={profId}
          onChange={(e) => setProfId(e.target.value)}
          className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal"
        >
          <option value="">Todos los profesionales</option>
          {profesionales.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
        </select>
      </div>

      {/* Resumen del día */}
      <div className="px-5 pt-3 flex flex-wrap gap-1.5">
        <span className="rounded-full bg-ink text-white text-[11px] font-semibold px-2.5 py-1">{data?.total ?? 0} citas</span>
        {Object.entries(resumen).map(([e, n]) => {
          const m = estadoMeta(e);
          return <span key={e} className={`rounded-full text-[11px] font-semibold px-2.5 py-1 ${m.chip}`}>{m.label}: {n}</span>;
        })}
      </div>

      {/* Lista de citas */}
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2">
        {data && data.citas.length === 0 && <div className="text-center text-sm text-sub py-10">Sin citas este día.</div>}
        {data?.citas.map((c) => {
          const m = estadoMeta(c.estado);
          return (
            <button
              key={c.id}
              onClick={() => { setSel(c); setError(null); }}
              className="text-left rounded-2xl border border-border bg-white px-4 py-3 flex items-center gap-3"
            >
              <div className="text-center shrink-0 w-12">
                <div className="text-[13px] font-bold text-ink tabular-nums">{hhmm(c.inicio)}</div>
                <div className="text-[10px] text-sub tabular-nums">{hhmm(c.fin)}</div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{c.paciente_nombre}</div>
                <div className="text-xs text-sub truncate">{c.profesional_nombre}{c.servicio_nombre ? ` · ${c.servicio_nombre}` : ''}</div>
                <div className="mt-1.5 flex items-center gap-2">
                  <span className={`inline-flex items-center gap-1 rounded-full text-[11px] font-semibold px-2 py-0.5 ${m.chip}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />{m.label}
                  </span>
                  <span className={`text-[11px] font-semibold ${c.facturado ? 'text-teal-dark' : 'text-sub'}`}>
                    {c.facturado ? `Facturado ${money(c.monto)}` : c.monto != null ? `Estimado ${money(c.monto)}` : 'Sin cargo'}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Hoja de acciones sobre la cita */}
      {sel && (
        <BottomSheet onClose={() => setSel(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">{sel.paciente_nombre}</div>
          <div className="text-[12.5px] text-sub">
            {hhmm(sel.inicio)}–{hhmm(sel.fin)} · {sel.profesional_nombre}{sel.servicio_nombre ? ` · ${sel.servicio_nombre}` : ''}
          </div>
          <div className="rounded-xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12.5px] text-teal-dark">
            Situación: {sel.facturado ? `facturado ${money(sel.monto)}` : sel.monto != null ? `estimado ${money(sel.monto)} (aún no facturado)` : 'sin cargo'}.
          </div>
          {sel.estado === 'completada' ? (
            <div className="text-[12.5px] text-sub">Esta cita ya fue cerrada por el médico; su estado no se cambia desde aquí.</div>
          ) : (
            <>
              <div className="text-[12px] font-semibold text-ink pt-1">Cambiar estado</div>
              <div className="grid grid-cols-2 gap-2">
                {ACCIONES.filter((a) => a.estado !== sel.estado).map((a) => (
                  <Button key={a.estado} onClick={() => cambiar(sel.id, a.estado)} variant="outline" className="text-[12.5px] py-2">{a.label}</Button>
                ))}
              </div>
            </>
          )}
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={() => setSel(null)} variant="ghost" className="w-full">Cerrar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
