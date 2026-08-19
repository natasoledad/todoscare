import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import { money } from '../../lib/citas';
import type { CuentaPorPagar, LabDental, LabOrden, LabPrestacion } from '../../api/types';

const inputCls = 'w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal';

type Tab = 'labs' | 'ordenes' | 'cuentas';
const TABS: { id: Tab; label: string }[] = [
  { id: 'labs', label: 'Laboratorios' },
  { id: 'ordenes', label: 'Órdenes' },
  { id: 'cuentas', label: 'Por pagar' },
];

const ORDEN_ESTADOS: Record<string, { label: string; cls: string }> = {
  solicitado: { label: 'Solicitado', cls: 'bg-[#EEF2F1] text-sub' },
  en_proceso: { label: 'En proceso', cls: 'bg-warn-bg text-[#8A6A00]' },
  en_revision: { label: 'En revisión', cls: 'bg-warn-bg text-[#8A6A00]' },
  terminado: { label: 'Terminado', cls: 'bg-teal-soft text-teal-dark' },
  cancelado: { label: 'Cancelado', cls: 'bg-[#F6EDEA] text-danger' },
};
const SIGUIENTE_ORDEN: Record<string, { estado: string; label: string }[]> = {
  solicitado: [{ estado: 'en_proceso', label: 'Iniciar' }, { estado: 'cancelado', label: 'Cancelar' }],
  en_proceso: [{ estado: 'en_revision', label: 'A revisión' }, { estado: 'cancelado', label: 'Cancelar' }],
  en_revision: [{ estado: 'terminado', label: 'Terminar' }, { estado: 'en_proceso', label: 'Rehacer' }],
};

export function Laboratorios() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('labs');
  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Laboratorios dentales" onBack={() => navigate('/empresa')} />
      <div className="px-5 pt-3">
        <div className="flex gap-1.5">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`rounded-full px-3.5 py-1.5 text-[12.5px] font-semibold ${tab === t.id ? 'bg-teal text-white' : 'bg-[#EEF2F1] text-sub'}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {tab === 'labs' && <LabsList />}
      {tab === 'ordenes' && <Ordenes />}
      {tab === 'cuentas' && <Cuentas />}
    </div>
  );
}

function LabsList() {
  const [labs, setLabs] = useState<LabDental[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', rut: '', contacto: '' });
  const [saving, setSaving] = useState(false);
  const [detalle, setDetalle] = useState<LabDental | null>(null);

  const load = () => api.labs.lista().then(setLabs);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    try {
      await api.labs.crear({ nombre: form.nombre.trim(), rut: form.rut.trim() || undefined, contacto: form.contacto.trim() || undefined });
      setOpen(false); setForm({ nombre: '', rut: '', contacto: '' }); await load();
    } finally { setSaving(false); }
  };

  return (
    <div className="flex-1 flex flex-col relative min-h-0">
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {labs.length === 0 && <div className="text-center text-sm text-sub py-8">Sin laboratorios. Agrega el primero.</div>}
        {labs.map((l) => (
          <div key={l.id} className={`rounded-2xl border border-border bg-white px-4 py-3 ${l.activo ? '' : 'opacity-60'}`}>
            <div className="flex items-center justify-between">
              <div className="font-semibold text-[14px] text-ink">{l.nombre}</div>
              <button onClick={() => setDetalle(l)} className="text-[12px] font-semibold text-teal-dark">Prestaciones ›</button>
            </div>
            <div className="text-[11px] text-sub mt-0.5">{[l.rut, l.contacto].filter(Boolean).join(' · ') || 'Sin datos de contacto'}</div>
            <button onClick={async () => { await api.labs.eliminar(l.id); await load(); }} className="mt-1 text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nuevo laboratorio</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo laboratorio</div>
          <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre / razón social" className={inputCls} />
          <input value={form.rut} onChange={(e) => setForm((f) => ({ ...f, rut: e.target.value }))} placeholder="RUT (opcional)" className={inputCls} />
          <input value={form.contacto} onChange={(e) => setForm((f) => ({ ...f, contacto: e.target.value }))} placeholder="Contacto (email/teléfono)" className={inputCls} />
          <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear laboratorio'}</Button>
        </BottomSheet>
      )}

      {detalle && <PrestacionesSheet lab={detalle} onClose={() => setDetalle(null)} />}
    </div>
  );
}

function PrestacionesSheet({ lab, onClose }: { lab: LabDental; onClose: () => void }) {
  const [servicios, setServicios] = useState<LabPrestacion[]>([]);
  const [form, setForm] = useState({ nombre: '', costo: '', precio: '' });
  const [saving, setSaving] = useState(false);

  const load = () => api.labs.servicios(lab.id).then(setServicios);
  useEffect(() => { load(); }, [lab.id]);

  const crear = async () => {
    setSaving(true);
    try {
      await api.labs.crearServicio(lab.id, { nombre: form.nombre.trim(), costo: Number(form.costo) || 0, precio: Number(form.precio) || 0 });
      setForm({ nombre: '', costo: '', precio: '' }); await load();
    } finally { setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{lab.nombre}</div>
      <div className="text-[12px] font-semibold text-sub">Prestaciones · costo vs precio</div>
      {servicios.length === 0 && <div className="text-[12px] text-sub">Sin prestaciones aún.</div>}
      <div className="flex flex-col gap-1.5">
        {servicios.map((s) => (
          <div key={s.id} className="rounded-xl bg-[#F6FBF9] px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[13px] text-ink">{s.nombre}</span>
              <button onClick={async () => { await api.labs.eliminarServicio(s.id); await load(); }} className="text-[11px] font-semibold text-danger">Quitar</button>
            </div>
            <div className="flex justify-between text-[11.5px] text-sub mt-0.5 tabular-nums">
              <span>Costo {money(s.costo)}</span>
              <span>Precio {money(s.precio)}</span>
              <span className="text-teal-dark font-semibold">Margen {money(s.margen)}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="text-[12px] font-semibold text-ink mt-2">Agregar prestación</div>
      <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre (ej. Corona de circonio)" className={inputCls} />
      <div className="flex gap-2">
        <input value={form.costo} onChange={(e) => setForm((f) => ({ ...f, costo: e.target.value }))} inputMode="numeric" placeholder="Costo (al lab)" className={inputCls} />
        <input value={form.precio} onChange={(e) => setForm((f) => ({ ...f, precio: e.target.value }))} inputMode="numeric" placeholder="Precio (al paciente)" className={inputCls} />
      </div>
      <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Guardando…' : 'Agregar prestación'}</Button>
    </BottomSheet>
  );
}

// ─────────────────────────── Órdenes de trabajo ───────────────────────────
function Ordenes() {
  const [ordenes, setOrdenes] = useState<LabOrden[]>([]);
  const [labs, setLabs] = useState<LabDental[]>([]);
  const [filtro, setFiltro] = useState('');
  const [open, setOpen] = useState(false);

  const load = () => api.labs.ordenes(filtro ? { estado: filtro } : undefined).then(setOrdenes);
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [filtro]);
  useEffect(() => { api.labs.lista().then(setLabs); }, []);

  const transicion = async (o: LabOrden, estado: string) => { await api.labs.cambiarEstadoOrden(o.id, estado); await load(); };
  const pagar = async (o: LabOrden) => { await api.labs.pagarOrden(o.id); await load(); };

  return (
    <div className="flex-1 flex flex-col relative min-h-0">
      <div className="px-5 pt-2">
        <select value={filtro} onChange={(e) => setFiltro(e.target.value)} className="rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-1.5 text-[12.5px] text-ink outline-none focus:border-teal">
          <option value="">Todos los estados</option>
          {Object.entries(ORDEN_ESTADOS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
      </div>
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {ordenes.length === 0 && <div className="text-center text-sm text-sub py-8">Sin órdenes.</div>}
        {ordenes.map((o) => {
          const meta = ORDEN_ESTADOS[o.estado] ?? { label: o.estado, cls: 'bg-[#EEF2F1] text-sub' };
          return (
            <div key={o.id} className="rounded-2xl border border-border bg-white px-4 py-3">
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-[14px] text-ink truncate">{o.descripcion}{o.pieza ? ` · ${o.pieza}` : ''}</div>
                <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${meta.cls}`}>{meta.label}</span>
              </div>
              <div className="text-[11px] text-sub mt-0.5">{o.lab_nombre}{o.paciente_nombre ? ` · ${o.paciente_nombre}` : ''} · costo {money(o.costo)}{o.pagado ? ' · pagado ✓' : ''}</div>
              <div className="mt-2 flex gap-2 flex-wrap">
                {(SIGUIENTE_ORDEN[o.estado] ?? []).map((a) => (
                  <button key={a.estado} onClick={() => transicion(o, a.estado)} className="rounded-lg bg-[#EEF2F1] px-3 py-1.5 text-[12px] font-semibold text-ink">{a.label}</button>
                ))}
                {o.estado === 'terminado' && !o.pagado && (
                  <button onClick={() => pagar(o)} className="rounded-lg bg-teal-soft px-3 py-1.5 text-[12px] font-semibold text-teal-dark">Pagar al lab</button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} disabled={labs.length === 0} className="w-full">+ Nueva orden</Button>
      </div>
      {open && <NuevaOrdenSheet labs={labs} onClose={() => setOpen(false)} onDone={async () => { setOpen(false); await load(); }} />}
    </div>
  );
}

function NuevaOrdenSheet({ labs, onClose, onDone }: { labs: LabDental[]; onClose: () => void; onDone: () => Promise<void> }) {
  const [labId, setLabId] = useState(labs[0]?.id ?? '');
  const [servicios, setServicios] = useState<LabPrestacion[]>([]);
  const [servicioId, setServicioId] = useState('');
  const [descripcion, setDescripcion] = useState('');
  const [pieza, setPieza] = useState('');
  const [costo, setCosto] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (labId) api.labs.servicios(labId).then(setServicios); else setServicios([]); }, [labId]);

  const elegirServicio = (id: string) => {
    setServicioId(id);
    const s = servicios.find((x) => x.id === id);
    if (s) { setCosto(String(s.costo)); if (!descripcion.trim()) setDescripcion(s.nombre); }
  };

  const crear = async () => {
    setSaving(true); setError(null);
    try {
      await api.labs.crearOrden({
        lab_id: labId, descripcion: descripcion.trim(), lab_service_id: servicioId || undefined,
        pieza: pieza.trim() || undefined, costo: costo ? Number(costo) : undefined,
      });
      await onDone();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la orden'); }
    finally { setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Nueva orden de laboratorio</div>
      <select value={labId} onChange={(e) => setLabId(e.target.value)} className={inputCls}>
        {labs.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
      </select>
      {servicios.length > 0 && (
        <select value={servicioId} onChange={(e) => elegirServicio(e.target.value)} className={inputCls}>
          <option value="">Prestación (opcional, prefija costo)</option>
          {servicios.map((s) => <option key={s.id} value={s.id}>{s.nombre} · {money(s.costo)}</option>)}
        </select>
      )}
      <input value={descripcion} onChange={(e) => setDescripcion(e.target.value)} placeholder="Descripción del trabajo" className={inputCls} />
      <div className="flex gap-2">
        <input value={pieza} onChange={(e) => setPieza(e.target.value)} placeholder="Pieza (FDI)" className={inputCls} />
        <input value={costo} onChange={(e) => setCosto(e.target.value)} inputMode="numeric" placeholder="Costo al lab" className={inputCls} />
      </div>
      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={crear} disabled={saving || !labId || !descripcion.trim()} className="w-full">{saving ? 'Creando…' : 'Crear orden'}</Button>
    </BottomSheet>
  );
}

// ─────────────────────────── Cuentas por pagar ───────────────────────────
function Cuentas() {
  const [cuentas, setCuentas] = useState<CuentaPorPagar[]>([]);
  useEffect(() => { api.labs.cuentasPorPagar().then(setCuentas); }, []);
  const total = cuentas.reduce((s, c) => s + c.total, 0);

  return (
    <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-10 flex flex-col gap-2.5">
      {cuentas.length === 0 && <div className="text-center text-sm text-sub py-8">Sin cuentas por pagar.</div>}
      {cuentas.length > 0 && (
        <div className="rounded-2xl bg-teal-soft border border-teal/30 px-4 py-3 flex items-center justify-between">
          <span className="font-heading font-bold text-[13px] text-teal-dark">Total por pagar</span>
          <span className="font-heading font-extrabold text-[18px] text-teal-dark tabular-nums">{money(total)}</span>
        </div>
      )}
      {cuentas.map((c) => (
        <div key={c.lab_id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
          <div>
            <div className="font-semibold text-[14px] text-ink">{c.lab_nombre}</div>
            <div className="text-[11px] text-sub">{c.cantidad_ordenes} orden(es) pendiente(s)</div>
          </div>
          <span className="font-semibold text-[14px] text-ink tabular-nums">{money(c.total)}</span>
        </div>
      ))}
    </div>
  );
}
