import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import type { AgendaOnlineConfig, AgendaOnlineDashboard, ServicioAdmin, SolicitudOnline } from '../../api/types';

const pct = (n: number) => `${Math.round(n * 100)}%`;

function ConversionDashboard() {
  const [d, setD] = useState<AgendaOnlineDashboard | null>(null);
  useEffect(() => { api.empresa.agendaOnlineDashboard(30).then(setD).catch(() => setD(null)); }, []);
  if (!d) return null;
  const pasos = [
    { label: 'Visitas', value: d.visitas },
    { label: 'Solicitudes', value: d.solicitudes },
    { label: 'Confirmadas', value: d.confirmadas },
  ];
  return (
    <div className="rounded-2xl border border-border bg-white px-4 py-4 flex flex-col gap-3">
      <div>
        <div className="font-heading font-bold text-[14px] text-ink">Conversión (últimos {d.dias} días)</div>
        <div className="text-[11px] text-sub">Del visitante a la hora confirmada.</div>
      </div>
      <div className="flex items-stretch gap-1.5">
        {pasos.map((p, i) => (
          <div key={p.label} className="flex-1 rounded-xl bg-[#F6FBF9] px-2 py-2.5 text-center">
            <div className="font-heading font-extrabold text-[19px] text-teal-dark tabular-nums">{p.value}</div>
            <div className="text-[10.5px] text-sub">{p.label}</div>
            {i < pasos.length - 1 && <div className="text-[9px] text-sub mt-0.5">▼</div>}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <div className="flex-1 rounded-xl bg-teal-soft px-3 py-2 text-center">
          <div className="font-bold text-[15px] text-teal-dark tabular-nums">{pct(d.tasa_conversion)}</div>
          <div className="text-[10.5px] text-sub">Visita → solicitud</div>
        </div>
        <div className="flex-1 rounded-xl bg-teal-soft px-3 py-2 text-center">
          <div className="font-bold text-[15px] text-teal-dark tabular-nums">{pct(d.tasa_confirmacion)}</div>
          <div className="text-[10.5px] text-sub">Solicitud → confirmada</div>
        </div>
      </div>
      {(d.pendientes > 0 || d.rechazadas > 0) && (
        <div className="text-[11px] text-sub">Pendientes: {d.pendientes} · Rechazadas: {d.rechazadas}</div>
      )}
    </div>
  );
}

const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString('es-CL', { weekday: 'short', day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

/** Panel de la agenda online pública (60): configuración, servicios reservables
 *  y bandeja de solicitudes de hora que el personal confirma o rechaza. */
export function AgendaOnline() {
  const navigate = useNavigate();
  const [cfg, setCfg] = useState<AgendaOnlineConfig | null>(null);
  const [servicios, setServicios] = useState<ServicioAdmin[]>([]);
  const [solicitudes, setSolicitudes] = useState<SolicitudOnline[]>([]);
  const [slug, setSlug] = useState('');
  const [mensaje, setMensaje] = useState('');
  const [antic, setAntic] = useState('2');
  const [ventana, setVentana] = useState('30');
  const [prepago, setPrepago] = useState(false);
  const [montoPrepago, setMontoPrepago] = useState('0');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const loadCfg = () => api.empresa.agendaOnline().then((c) => {
    setCfg(c); setSlug(c.slug || ''); setMensaje(c.mensaje || '');
    setAntic(String(c.anticipacion_horas)); setVentana(String(c.ventana_dias));
    setPrepago(c.requiere_prepago); setMontoPrepago(String(c.monto_prepago));
  });
  const loadServicios = () => api.empresa.servicios().then(setServicios);
  const loadSolicitudes = () => api.empresa.solicitudes('pendiente').then(setSolicitudes);
  useEffect(() => { loadCfg(); loadServicios(); loadSolicitudes(); }, []);

  const guardar = async (patch: Partial<{ habilitada: boolean }> = {}) => {
    setSaving(true); setError(null);
    try {
      const c = await api.empresa.guardarAgendaOnline({
        slug: slug.trim() || undefined, mensaje: mensaje.trim() || undefined,
        anticipacion_horas: Number(antic) || 0, ventana_dias: Number(ventana) || 30,
        requiere_prepago: prepago, monto_prepago: Number(montoPrepago) || 0, ...patch,
      });
      setCfg(c); setSlug(c.slug || '');
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.'); }
    finally { setSaving(false); }
  };

  const toggleReservable = async (s: ServicioAdmin) => {
    await api.empresa.marcarReservable(s.id, !s.reservable_online);
    await loadServicios();
  };

  const confirmar = async (id: string) => {
    setBusy(id); setError(null);
    try { await api.empresa.confirmarSolicitud(id); await loadSolicitudes(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo confirmar.'); }
    finally { setBusy(null); }
  };
  const rechazar = async (id: string) => {
    setBusy(id);
    try { await api.empresa.rechazarSolicitud(id); await loadSolicitudes(); }
    finally { setBusy(null); }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Agenda online" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-10 flex flex-col gap-5">

        {/* Configuración */}
        <div className="rounded-2xl border border-border bg-white px-4 py-4 flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-heading font-bold text-[14px] text-ink">Reserva en línea</div>
              <div className="text-[11px] text-sub">Publica tu agenda para que reserven sin cuenta.</div>
            </div>
            <button onClick={() => guardar({ habilitada: !cfg?.habilitada })} disabled={saving}
              className={`rounded-full px-3 py-1.5 text-[12px] font-semibold ${cfg?.habilitada ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
              {cfg?.habilitada ? 'Habilitada' : 'Deshabilitada'}
            </button>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-sub">Enlace público</label>
            <div className="flex items-center gap-1.5 mt-1">
              <span className="text-[12px] text-sub">/reservar/</span>
              <input value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))} placeholder="mi-clinica"
                className="flex-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-teal" />
            </div>
          </div>

          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-[11px] font-semibold text-sub">Anticipación (horas)</label>
              <input value={antic} onChange={(e) => setAntic(e.target.value)} inputMode="numeric"
                className="w-full mt-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-teal" />
            </div>
            <div className="flex-1">
              <label className="text-[11px] font-semibold text-sub">Ventana (días)</label>
              <input value={ventana} onChange={(e) => setVentana(e.target.value)} inputMode="numeric"
                className="w-full mt-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-teal" />
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-sub">Mensaje al paciente</label>
            <input value={mensaje} onChange={(e) => setMensaje(e.target.value)} placeholder="Reserva tu hora; te confirmaremos pronto."
              className="w-full mt-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-teal" />
          </div>

          {/* Prepago al agendar (61.7) */}
          <div className="rounded-xl bg-[#F6FBF9] px-3 py-2.5">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-[12.5px] font-semibold text-ink">Exigir prepago al reservar</span>
              <input type="checkbox" checked={prepago} onChange={(e) => setPrepago(e.target.checked)} className="w-4 h-4 accent-teal" />
            </label>
            <div className="text-[10.5px] text-sub mt-0.5">Reduce inasistencias: el paciente paga un monto para confirmar.</div>
            {prepago && (
              <div className="mt-2">
                <label className="text-[11px] font-semibold text-sub">Monto del prepago (CLP)</label>
                <input value={montoPrepago} onChange={(e) => setMontoPrepago(e.target.value)} inputMode="numeric"
                  className="w-full mt-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-sm text-ink outline-none focus:border-teal" />
              </div>
            )}
          </div>

          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={() => guardar()} disabled={saving} className="w-full">{saving ? 'Guardando…' : 'Guardar configuración'}</Button>
        </div>

        {/* Dashboard de conversión (60.12) */}
        <ConversionDashboard />

        {/* Servicios reservables */}
        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Servicios reservables en línea</div>
          <div className="flex flex-col gap-2">
            {servicios.map((s) => (
              <button key={s.id} onClick={() => toggleReservable(s)}
                className="flex items-center justify-between rounded-xl border border-border bg-white px-3.5 py-2.5 text-left">
                <span className="text-[13px] text-ink">{s.nombre}</span>
                <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${s.reservable_online ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                  {s.reservable_online ? 'Visible' : 'Oculto'}
                </span>
              </button>
            ))}
            {servicios.length === 0 && <div className="text-sm text-sub">Sin servicios en el catálogo.</div>}
          </div>
        </div>

        {/* Solicitudes pendientes */}
        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Solicitudes pendientes ({solicitudes.length})</div>
          <div className="flex flex-col gap-2">
            {solicitudes.length === 0 && <div className="text-sm text-sub">No hay solicitudes pendientes.</div>}
            {solicitudes.map((s) => (
              <div key={s.id} className="rounded-2xl border border-border bg-white px-4 py-3">
                <div className="flex items-center justify-between">
                  <div className="font-semibold text-[14px] text-ink">{s.paciente_nombre}</div>
                  <span className="font-mono text-[11px] text-teal-dark">{s.codigo}</span>
                </div>
                <div className="text-[11px] text-sub mt-0.5 capitalize">{fechaHora(s.inicio)} · {s.servicio_nombre || 'Servicio'} · {s.profesional_nombre}</div>
                <div className="text-[11px] text-sub mt-0.5">
                  {s.paciente_rut && <>RUT {s.paciente_rut} · </>}{s.paciente_telefono || s.paciente_email || 'Sin contacto'}
                </div>
                {s.notas && <div className="text-[12px] text-ink mt-1 italic">“{s.notas}”</div>}
                <div className="mt-2.5 flex gap-2">
                  <Button onClick={() => confirmar(s.id)} disabled={busy === s.id} className="text-[12px] py-1.5 px-3">Confirmar</Button>
                  <Button onClick={() => rechazar(s.id)} disabled={busy === s.id} variant="outline" className="text-[12px] py-1.5 px-3">Rechazar</Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
