import { useEffect, useState } from 'react';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { DocumentoClinico, PlanItem, PlanTratamiento, SignosVitales } from '../../api/types';

const money = (n: number) => `$${n.toLocaleString('es-CL')}`;
const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: '2-digit' });

// ─────────────────────────── Signos vitales ───────────────────────────
const CAMPOS: { k: keyof SignosVitales; label: string; sufijo?: string }[] = [
  { k: 'presion_sistolica', label: 'PA sistólica', sufijo: 'mmHg' },
  { k: 'presion_diastolica', label: 'PA diastólica', sufijo: 'mmHg' },
  { k: 'fc_ppm', label: 'FC', sufijo: 'ppm' },
  { k: 'fr_rpm', label: 'FR', sufijo: 'rpm' },
  { k: 'spo2', label: 'SpO₂', sufijo: '%' },
  { k: 'temperatura', label: 'Temp.', sufijo: '°C' },
  { k: 'peso_kg', label: 'Peso', sufijo: 'kg' },
  { k: 'talla_cm', label: 'Talla', sufijo: 'cm' },
  { k: 'glicemia', label: 'Glicemia', sufijo: 'mg/dl' },
  { k: 'eva', label: 'Dolor (EVA)', sufijo: '/10' },
];

export function SignosVitalesSection({ patientId }: { patientId: string }) {
  const [lista, setLista] = useState<SignosVitales[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.medico.signos(patientId).then(setLista);
  useEffect(() => { load(); }, [patientId]);

  const guardar = async () => {
    setSaving(true); setError(null);
    try {
      const body: Record<string, number> = {};
      for (const [k, v] of Object.entries(f)) if (v !== '') body[k] = Number(v);
      await api.medico.registrarSignos(patientId, body);
      setOpen(false); setF({});
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar'); }
    finally { setSaving(false); }
  };

  const ultimo = lista[0];
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Signos vitales</div>
        <button onClick={() => { setOpen(true); setError(null); }} className="text-[12.5px] font-semibold text-teal-dark">+ Registrar</button>
      </div>
      {!ultimo && <div className="text-sm text-sub">Sin registros.</div>}
      {ultimo && (
        <div className="rounded-2xl border border-border bg-white px-4 py-3">
          <div className="text-[11px] text-sub mb-2">Última toma · {fecha(ultimo.fecha)}</div>
          <div className="grid grid-cols-3 gap-2">
            {CAMPOS.filter((c) => ultimo[c.k] != null).map((c) => (
              <div key={c.k}>
                <div className="text-[10.5px] text-sub">{c.label}</div>
                <div className="text-[15px] font-bold text-ink tabular-nums">{String(ultimo[c.k])}<span className="text-[10px] font-normal text-sub"> {c.sufijo}</span></div>
              </div>
            ))}
          </div>
          {lista.length > 1 && <div className="mt-2 text-[11px] text-sub">{lista.length} tomas registradas</div>}
        </div>
      )}

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Registrar signos vitales</div>
          <div className="text-[12px] text-sub">Completa solo lo que midas.</div>
          <div className="grid grid-cols-2 gap-2">
            {CAMPOS.map((c) => (
              <div key={c.k}>
                <div className="text-[11px] text-sub mb-0.5">{c.label} <span className="text-[10px]">{c.sufijo}</span></div>
                <input value={f[c.k] ?? ''} onChange={(e) => setF((p) => ({ ...p, [c.k]: e.target.value }))} inputMode="decimal"
                  className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" />
              </div>
            ))}
          </div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={guardar} disabled={saving} className="w-full">{saving ? 'Guardando…' : 'Guardar'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}

// ─────────────────────── Planes de tratamiento ───────────────────────
const PLAN_ESTADOS: Record<string, { label: string; tone: 'teal' | 'warn' }> = {
  propuesto: { label: 'Propuesto', tone: 'warn' },
  aceptado: { label: 'Aceptado', tone: 'teal' },
  en_curso: { label: 'En curso', tone: 'teal' },
  completado: { label: 'Completado', tone: 'teal' },
  rechazado: { label: 'Rechazado', tone: 'warn' },
};
const SIGUIENTE: Record<string, { estado: string; label: string }[]> = {
  propuesto: [{ estado: 'aceptado', label: 'Aceptar' }, { estado: 'rechazado', label: 'Rechazar' }],
  aceptado: [{ estado: 'en_curso', label: 'Iniciar' }],
  en_curso: [{ estado: 'completado', label: 'Completar' }],
};

type ItemForm = { descripcion: string; pieza: string; cantidad: string; precio_unit: string };

export function PlanesSection({ patientId }: { patientId: string }) {
  const [planes, setPlanes] = useState<PlanTratamiento[]>([]);
  const [open, setOpen] = useState(false);
  const [titulo, setTitulo] = useState('');
  const [items, setItems] = useState<ItemForm[]>([{ descripcion: '', pieza: '', cantidad: '1', precio_unit: '' }]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.medico.planes(patientId).then(setPlanes);
  useEffect(() => { load(); }, [patientId]);

  const totalForm = items.reduce((s, it) => s + (Number(it.cantidad) || 0) * (Number(it.precio_unit) || 0), 0);

  const crear = async () => {
    setSaving(true); setError(null);
    try {
      await api.medico.crearPlan(patientId, {
        titulo: titulo.trim(),
        items: items.filter((i) => i.descripcion.trim()).map((i) => ({
          descripcion: i.descripcion.trim(), pieza: i.pieza || undefined,
          cantidad: Number(i.cantidad) || 1, precio_unit: Number(i.precio_unit) || 0,
        })),
      });
      setOpen(false); setTitulo(''); setItems([{ descripcion: '', pieza: '', cantidad: '1', precio_unit: '' }]);
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el plan'); }
    finally { setSaving(false); }
  };

  const cambiarPlan = async (id: string, estado: string) => { await api.medico.cambiarEstadoPlan(id, estado); await load(); };
  const toggleItem = async (planId: string, item: PlanItem) => {
    await api.medico.cambiarEstadoItem(planId, item.id, item.estado === 'realizado' ? 'pendiente' : 'realizado');
    await load();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Planes de tratamiento</div>
        <button onClick={() => { setOpen(true); setError(null); }} className="text-[12.5px] font-semibold text-teal-dark">+ Nuevo plan</button>
      </div>
      {planes.length === 0 && <div className="text-sm text-sub">Sin planes.</div>}
      <div className="flex flex-col gap-2">
        {planes.map((p) => {
          const meta = PLAN_ESTADOS[p.estado] ?? { label: p.estado, tone: 'warn' as const };
          const realizados = p.items.filter((i) => i.estado === 'realizado').length;
          return (
            <div key={p.id} className="rounded-2xl border border-border bg-white px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="font-semibold text-[14px] text-ink">{p.titulo}</div>
                <StatusTag label={meta.label} tone={meta.tone} />
              </div>
              <div className="text-[11px] text-sub mt-0.5">{fecha(p.fecha)} · {realizados}/{p.items.length} ítems · Total {money(p.total)}</div>
              <div className="mt-2 flex flex-col gap-1">
                {p.items.map((it) => (
                  <button key={it.id} onClick={() => toggleItem(p.id, it)} className="flex items-center justify-between text-left">
                    <span className={`text-[12.5px] ${it.estado === 'realizado' ? 'text-sub line-through' : 'text-ink'}`}>
                      {it.estado === 'realizado' ? '✓ ' : '○ '}{it.descripcion}{it.pieza ? ` · ${it.pieza}` : ''}{it.cantidad > 1 ? ` ×${it.cantidad}` : ''}
                    </span>
                    <span className="text-[12px] text-sub tabular-nums">{money(it.subtotal)}</span>
                  </button>
                ))}
              </div>
              {SIGUIENTE[p.estado] && (
                <div className="mt-2.5 flex gap-2">
                  {SIGUIENTE[p.estado].map((a) => (
                    <Button key={a.estado} onClick={() => cambiarPlan(p.id, a.estado)} variant="outline" className="text-[12px] py-1.5 px-3">{a.label}</Button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo plan de tratamiento</div>
          <input value={titulo} onChange={(e) => setTitulo(e.target.value)} placeholder="Título del plan"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="text-[12px] font-semibold text-ink">Ítems / presupuesto</div>
          {items.map((it, idx) => (
            <div key={idx} className="flex flex-col gap-1.5 rounded-xl bg-[#F6FBF9] p-2.5">
              <input value={it.descripcion} onChange={(e) => setItems((p) => p.map((x, i) => i === idx ? { ...x, descripcion: e.target.value } : x))} placeholder="Descripción (ej. Endodoncia)"
                className="w-full rounded-lg border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" />
              <div className="flex gap-1.5">
                <input value={it.pieza} onChange={(e) => setItems((p) => p.map((x, i) => i === idx ? { ...x, pieza: e.target.value } : x))} placeholder="Pieza"
                  className="w-16 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" />
                <input value={it.cantidad} onChange={(e) => setItems((p) => p.map((x, i) => i === idx ? { ...x, cantidad: e.target.value } : x))} placeholder="Cant." inputMode="numeric"
                  className="w-16 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-sm text-ink outline-none focus:border-teal" />
                <input value={it.precio_unit} onChange={(e) => setItems((p) => p.map((x, i) => i === idx ? { ...x, precio_unit: e.target.value } : x))} placeholder="Precio unit." inputMode="numeric"
                  className="flex-1 rounded-lg border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" />
              </div>
            </div>
          ))}
          <button onClick={() => setItems((p) => [...p, { descripcion: '', pieza: '', cantidad: '1', precio_unit: '' }])} className="text-[12.5px] font-semibold text-teal-dark self-start">+ Agregar ítem</button>
          <div className="flex justify-between text-[13px] font-semibold text-ink"><span>Total</span><span className="tabular-nums">{money(totalForm)}</span></div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !titulo.trim()} className="w-full">{saving ? 'Creando…' : 'Crear plan'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}

// ─────────────────────── Documentos clínicos ───────────────────────
const DOC_TIPOS = [
  { id: 'consentimiento', label: 'Consentimiento' },
  { id: 'licencia', label: 'Licencia médica' },
  { id: 'interconsulta', label: 'Interconsulta' },
  { id: 'otro', label: 'Otro' },
];
const docLabel = (id: string) => DOC_TIPOS.find((t) => t.id === id)?.label ?? id;

export function DocumentosSection({ patientId }: { patientId: string }) {
  const [docs, setDocs] = useState<DocumentoClinico[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ tipo: 'consentimiento', titulo: '', contenido: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.medico.documentos(patientId).then(setDocs);
  useEffect(() => { load(); }, [patientId]);

  const crear = async () => {
    setSaving(true); setError(null);
    try {
      await api.medico.crearDocumento(patientId, { tipo: f.tipo, titulo: f.titulo.trim(), contenido: f.contenido || undefined });
      setOpen(false); setF({ tipo: 'consentimiento', titulo: '', contenido: '' });
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear'); }
    finally { setSaving(false); }
  };
  const anular = async (id: string) => { await api.medico.anularDocumento(id); await load(); };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Documentos clínicos</div>
        <button onClick={() => { setOpen(true); setError(null); }} className="text-[12.5px] font-semibold text-teal-dark">+ Nuevo</button>
      </div>
      {docs.length === 0 && <div className="text-sm text-sub">Sin documentos.</div>}
      <div className="flex flex-col gap-2">
        {docs.map((d) => (
          <div key={d.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <div className="font-semibold text-[13.5px] text-ink truncate">{d.titulo}</div>
                <div className="text-[11px] text-sub">{docLabel(d.tipo)} · {fecha(d.fecha)}</div>
              </div>
              <StatusTag label={d.estado === 'anulado' ? 'Anulado' : 'Emitido'} tone={d.estado === 'anulado' ? 'warn' : 'teal'} />
            </div>
            {d.contenido && <div className="mt-1.5 text-[12px] text-sub line-clamp-2">{d.contenido}</div>}
            {d.estado !== 'anulado' && (
              <button onClick={() => anular(d.id)} className="mt-1.5 text-[11.5px] font-semibold text-danger">Anular</button>
            )}
          </div>
        ))}
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo documento</div>
          <select value={f.tipo} onChange={(e) => setF((p) => ({ ...p, tipo: e.target.value }))}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            {DOC_TIPOS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <input value={f.titulo} onChange={(e) => setF((p) => ({ ...p, titulo: e.target.value }))} placeholder="Título"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <textarea value={f.contenido} onChange={(e) => setF((p) => ({ ...p, contenido: e.target.value }))} placeholder="Contenido (opcional)" rows={4}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !f.titulo.trim()} className="w-full">{saving ? 'Guardando…' : 'Emitir documento'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}

// ─────────────────────── Periodontograma ───────────────────────
const FDI_SUP = ['1.8', '1.7', '1.6', '1.5', '1.4', '1.3', '1.2', '1.1', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8'];
const FDI_INF = ['4.8', '4.7', '4.6', '4.5', '4.4', '4.3', '4.2', '4.1', '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8'];
const PS_CICLO = [undefined, 2, 4, 6]; // normal, leve, moderado, profundo
const psColor = (ps?: number) => (ps == null ? 'bg-[#F2F6F5] text-sub' : ps >= 6 ? 'bg-[#F6D9CF] text-danger' : ps >= 4 ? 'bg-warn-bg text-warn' : 'bg-teal-soft text-teal-dark');

type PerioDatos = Record<string, { ps?: number; sangrado?: boolean }>;

export function PeriodontogramaSection({ patientId }: { patientId: string }) {
  const [datos, setDatos] = useState<PerioDatos>({});
  const [anteriores, setAnteriores] = useState(0);
  const [modo, setModo] = useState<'ps' | 'sangrado'>('ps');
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.medico.periodontograma(patientId).then((p) => {
      setDatos(p?.datos ?? {});
      setAnteriores(p ? p.tomas_anteriores + 1 : 0);
      setDirty(false);
    });
  }, [patientId]);

  const tap = (t: string) => {
    setDatos((prev) => {
      const cur = prev[t] ?? {};
      if (modo === 'sangrado') return { ...prev, [t]: { ...cur, sangrado: !cur.sangrado } };
      const idx = PS_CICLO.indexOf(cur.ps);
      return { ...prev, [t]: { ...cur, ps: PS_CICLO[(idx + 1) % PS_CICLO.length] } };
    });
    setDirty(true);
  };

  const guardar = async () => {
    setSaving(true);
    try { const p = await api.medico.guardarPeriodontograma(patientId, datos); setAnteriores(p.tomas_anteriores + 1); setDirty(false); }
    finally { setSaving(false); }
  };

  const Diente = ({ t }: { t: string }) => {
    const d = datos[t] ?? {};
    return (
      <button onClick={() => tap(t)} className={`relative aspect-square rounded-md border border-border-strong text-[10px] font-bold tabular-nums flex items-center justify-center ${psColor(d.ps)}`}>
        {d.ps ?? ''}
        {d.sangrado && <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-danger" />}
      </button>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Periodontograma</div>
        {anteriores > 0 && <span className="text-[11px] text-sub">{anteriores} toma{anteriores === 1 ? '' : 's'}</span>}
      </div>
      <div className="text-[11.5px] text-sub mb-2">
        Toca un diente para {modo === 'ps' ? 'registrar profundidad de surco (mm)' : 'marcar sangrado'}.
      </div>
      <div className="flex gap-2 mb-2 text-[12px]">
        <button onClick={() => setModo('ps')} className={`rounded-full px-3 py-1 font-semibold border ${modo === 'ps' ? 'bg-teal text-white border-teal' : 'bg-white text-sub border-border'}`}>Profundidad</button>
        <button onClick={() => setModo('sangrado')} className={`rounded-full px-3 py-1 font-semibold border ${modo === 'sangrado' ? 'bg-danger text-white border-danger' : 'bg-white text-sub border-border'}`}>Sangrado</button>
      </div>
      <div className="bg-white border border-border rounded-2xl p-3 flex flex-col gap-1.5">
        <div className="grid grid-cols-8 gap-1">{FDI_SUP.map((t) => <Diente key={t} t={t} />)}</div>
        <div className="text-[10px] text-sub text-center">— maxilar superior / inferior —</div>
        <div className="grid grid-cols-8 gap-1">{FDI_INF.map((t) => <Diente key={t} t={t} />)}</div>
      </div>
      <div className="mt-1.5 flex items-center gap-3 text-[10.5px] text-sub">
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-teal-soft inline-block" /> ≤3</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-warn-bg inline-block" /> 4-5</span>
        <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded bg-[#F6D9CF] inline-block" /> ≥6</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-danger inline-block" /> sangrado</span>
      </div>
      {dirty && <Button onClick={guardar} disabled={saving} className="w-full mt-2.5">{saving ? 'Guardando…' : 'Guardar toma'}</Button>}
    </div>
  );
}
