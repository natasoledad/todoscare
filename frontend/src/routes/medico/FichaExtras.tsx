import { useEffect, useState } from 'react';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import { money } from '../../lib/citas';
import type { BloqueDoc, Cie10Item, Diagnostico, DocumentoClinico, OdontogramaCatalogo, OdontogramaPieza, OdontogramaPiezas, PerioDatos, PerioPieza, PerioSitio, PlantillaDoc, PlanItem, PlanTratamiento, SignosVitales, TimelineEvento } from '../../api/types';

const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: '2-digit' });

// ─────────────────────── Timeline clínico unificado (70.1) ───────────────────────
const TIMELINE_TIPO: Record<string, string> = {
  prontuario: 'Atención', prescripcion: 'Receta', orden_examen: 'Examen',
  plan: 'Plan', periodontograma: 'Periodoncia', documento: 'Documento', signos: 'Signos vitales',
};

export function TimelineSection({ patientId }: { patientId: string }) {
  const [eventos, setEventos] = useState<TimelineEvento[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => { api.medico.timeline(patientId).then((e) => { setEventos(e); setLoaded(true); }).catch(() => setLoaded(true)); }, [patientId]);

  if (!loaded) return null;

  return (
    <div>
      <div className="font-heading font-bold text-[13px] text-ink mb-2">Historia clínica</div>
      {eventos.length === 0 ? (
        <div className="text-sm text-sub">Sin eventos clínicos registrados.</div>
      ) : (
        <div className="relative pl-5">
          <div className="absolute left-[7px] top-1 bottom-1 w-px bg-border" />
          <div className="flex flex-col gap-3">
            {eventos.map((e, i) => (
              <div key={i} className="relative">
                <div className="absolute -left-5 top-0.5 w-[15px] h-[15px] rounded-full bg-white border-2 border-teal grid place-items-center text-[8px]">{e.icono}</div>
                <div className="flex items-center justify-between">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-teal-dark">{TIMELINE_TIPO[e.tipo] ?? e.tipo}</div>
                  <div className="text-[10.5px] text-sub">{fecha(e.fecha)}</div>
                </div>
                <div className="font-semibold text-[13.5px] text-ink leading-snug">{e.titulo}</div>
                {e.resumen && <div className="text-[12px] text-sub">{e.resumen}</div>}
                {e.estado && <span className="inline-block mt-0.5 rounded-full bg-[#EEF2F1] px-2 py-0.5 text-[10px] font-semibold text-sub">{e.estado}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

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

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Planes de tratamiento</div>
        <button onClick={() => { setOpen(true); setError(null); }} className="text-[12.5px] font-semibold text-teal-dark">+ Nuevo plan</button>
      </div>
      {planes.length === 0 && <div className="text-sm text-sub">Sin planes.</div>}
      <div className="flex flex-col gap-2">
        {planes.map((p) => <PlanCard key={p.id} plan={p} onChanged={load} />)}
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

function PlanCard({ plan, onChanged }: { plan: PlanTratamiento; onChanged: () => Promise<void> }) {
  const [editDesc, setEditDesc] = useState(false);
  const [descPct, setDescPct] = useState(String(Math.round((plan.descuento_pct || 0) * 100)));
  const [busy, setBusy] = useState(false);
  const meta = PLAN_ESTADOS[plan.estado] ?? { label: plan.estado, tone: 'warn' as const };
  const realizados = plan.items.filter((i) => i.estado === 'realizado').length;
  const r = plan.resumen;

  const cambiarPlan = async (estado: string) => { setBusy(true); try { await api.medico.cambiarEstadoPlan(plan.id, estado); await onChanged(); } finally { setBusy(false); } };
  const toggleItem = async (item: PlanItem) => {
    setBusy(true);
    try { await api.medico.cambiarEstadoItem(plan.id, item.id, item.estado === 'realizado' ? 'pendiente' : 'realizado'); await onChanged(); }
    finally { setBusy(false); }
  };
  const guardarDescuento = async () => {
    const pct = Math.max(0, Math.min(100, Number(descPct) || 0)) / 100;
    setBusy(true);
    try { await api.medico.editarPlan(plan.id, { descuento_pct: pct }); setEditDesc(false); await onChanged(); }
    finally { setBusy(false); }
  };

  return (
    <div className="rounded-2xl border border-border bg-white px-4 py-3">
      <div className="flex items-center justify-between">
        <div className="font-semibold text-[14px] text-ink">{plan.titulo}</div>
        <StatusTag label={meta.label} tone={meta.tone} />
      </div>
      <div className="text-[11px] text-sub mt-0.5">{fecha(plan.fecha)} · {realizados}/{plan.items.length} ítems</div>
      <div className="mt-2 flex flex-col gap-1">
        {plan.items.map((it) => (
          <button key={it.id} onClick={() => toggleItem(it)} disabled={busy} className="flex items-center justify-between text-left disabled:opacity-60">
            <span className={`text-[12.5px] ${it.estado === 'realizado' ? 'text-sub line-through' : 'text-ink'}`}>
              {it.estado === 'realizado' ? '✓ ' : '○ '}{it.descripcion}{it.pieza ? ` · ${it.pieza}` : ''}{it.cantidad > 1 ? ` ×${it.cantidad}` : ''}
            </span>
            <span className="text-[12px] text-sub tabular-nums">{money(it.subtotal)}</span>
          </button>
        ))}
      </div>

      {/* Resumen financiero (69.7) */}
      <div className="mt-3 rounded-xl bg-[#F6FBF9] px-3 py-2.5 flex flex-col gap-1 text-[12.5px]">
        <div className="flex justify-between text-ink"><span>Total bruto</span><span className="tabular-nums">{money(r.total_bruto)}</span></div>
        <div className="flex justify-between items-center text-sub">
          <button onClick={() => { setDescPct(String(Math.round((plan.descuento_pct || 0) * 100))); setEditDesc((v) => !v); }} className="text-teal-dark font-semibold">
            Descuento {Math.round((plan.descuento_pct || 0) * 100)}%
          </button>
          <span className="tabular-nums">−{money(r.descuento)}</span>
        </div>
        {editDesc && (
          <div className="flex items-center gap-2 py-1">
            <input value={descPct} onChange={(e) => setDescPct(e.target.value)} inputMode="numeric" placeholder="%"
              className="w-16 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-teal" />
            <span className="text-[12px] text-sub">%</span>
            <Button onClick={guardarDescuento} disabled={busy} className="text-[12px] py-1 px-3">Guardar</Button>
          </div>
        )}
        <div className="flex justify-between font-semibold text-ink border-t border-border pt-1 mt-0.5"><span>Neto</span><span className="tabular-nums">{money(r.total_neto)}</span></div>
        <div className="flex justify-between text-sub"><span>Abonado</span><span className="tabular-nums">{money(r.abonado)}</span></div>
        <div className="flex justify-between font-semibold text-ink"><span>Saldo</span><span className={`tabular-nums ${r.saldo > 0 ? 'text-danger' : 'text-teal-dark'}`}>{money(r.saldo)}</span></div>
        <div className="mt-1.5">
          <div className="flex justify-between text-[11px] text-sub mb-0.5"><span>Progreso clínico</span><span className="tabular-nums">{Math.round(r.progreso_pct * 100)}%</span></div>
          <div className="h-1.5 rounded-full bg-border overflow-hidden"><div className="h-full bg-teal rounded-full" style={{ width: `${Math.min(100, Math.round(r.progreso_pct * 100))}%` }} /></div>
        </div>
      </div>

      {SIGUIENTE[plan.estado] && (
        <div className="mt-2.5 flex gap-2">
          {SIGUIENTE[plan.estado].map((a) => (
            <Button key={a.estado} onClick={() => cambiarPlan(a.estado)} disabled={busy} variant="outline" className="text-[12px] py-1.5 px-3">{a.label}</Button>
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────── Documentos clínicos ───────────────────────
const DOC_TIPOS = [
  { id: 'consentimiento', label: 'Consentimiento' },
  { id: 'licencia', label: 'Licencia médica' },
  { id: 'interconsulta', label: 'Interconsulta' },
  { id: 'certificado', label: 'Certificado' },
  { id: 'otro', label: 'Otro' },
];
const docLabel = (id: string) => DOC_TIPOS.find((t) => t.id === id)?.label ?? id;

export function DocumentosSection({ patientId }: { patientId: string }) {
  const [docs, setDocs] = useState<DocumentoClinico[]>([]);
  const [plantillas, setPlantillas] = useState<PlantillaDoc[]>([]);
  const [open, setOpen] = useState(false);
  const [gestor, setGestor] = useState(false);
  const [tplId, setTplId] = useState('');
  const [f, setF] = useState({ tipo: 'consentimiento', titulo: '', contenido: '' });
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.medico.documentos(patientId).then(setDocs);
  const loadTpl = () => api.medico.plantillasDoc().then(setPlantillas).catch(() => setPlantillas([]));
  useEffect(() => { load(); loadTpl(); }, [patientId]);

  const tpl = plantillas.find((t) => t.id === tplId);
  const camposTpl = tpl ? tpl.bloques.filter((b) => b.tipo === 'campo') : [];

  const abrir = () => { setOpen(true); setError(null); setTplId(''); setCampos({}); setF({ tipo: 'consentimiento', titulo: '', contenido: '' }); };

  const crear = async () => {
    setSaving(true); setError(null);
    try {
      if (tpl) {
        await api.medico.crearDocumento(patientId, { tipo: tpl.tipo, titulo: f.titulo.trim() || tpl.nombre, template_id: tpl.id, campos });
      } else {
        await api.medico.crearDocumento(patientId, { tipo: f.tipo, titulo: f.titulo.trim(), contenido: f.contenido || undefined });
      }
      setOpen(false);
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear'); }
    finally { setSaving(false); }
  };
  const anular = async (id: string) => { await api.medico.anularDocumento(id); await load(); };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Documentos clínicos</div>
        <div className="flex gap-3">
          <button onClick={() => setGestor(true)} className="text-[12.5px] font-semibold text-sub">Plantillas</button>
          <button onClick={abrir} className="text-[12.5px] font-semibold text-teal-dark">+ Nuevo</button>
        </div>
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
            {d.contenido && <div className="mt-1.5 text-[12px] text-sub line-clamp-2 whitespace-pre-line">{d.contenido}</div>}
            {d.firma_profesional && (
              <div className="mt-2 flex items-center gap-2">
                <img src={d.firma_profesional} alt="Firma del profesional" className="h-9 object-contain" />
                <span className="text-[10.5px] text-sub">Firma del profesional</span>
              </div>
            )}
            {d.requiere_firma && (
              <div className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${d.firmado_paciente ? 'bg-teal-soft text-teal-dark' : 'bg-warn-bg text-[#8A6A00]'}`}>
                {d.firmado_paciente ? '✓ Firmado por el paciente' : 'Pendiente de firma'}
              </div>
            )}
            {d.estado !== 'anulado' && (
              <button onClick={() => anular(d.id)} className="mt-1.5 block text-[11.5px] font-semibold text-danger">Anular</button>
            )}
          </div>
        ))}
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo documento</div>
          {plantillas.length > 0 && (
            <select value={tplId} onChange={(e) => { setTplId(e.target.value); setCampos({}); }}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="">Sin plantilla (libre)</option>
              {plantillas.map((t) => <option key={t.id} value={t.id}>{t.nombre}{t.requiere_firma ? ' · firma' : ''}</option>)}
            </select>
          )}
          {!tpl && (
            <select value={f.tipo} onChange={(e) => setF((p) => ({ ...p, tipo: e.target.value }))}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              {DOC_TIPOS.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
            </select>
          )}
          <input value={f.titulo} onChange={(e) => setF((p) => ({ ...p, titulo: e.target.value }))} placeholder="Título"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {tpl ? (
            <div className="flex flex-col gap-1.5">
              {camposTpl.map((b, i) => (
                <input key={i} value={campos[b.clave || b.label || ''] || ''}
                  onChange={(e) => setCampos((c) => ({ ...c, [b.clave || b.label || '']: e.target.value }))}
                  placeholder={b.label || b.clave || 'Campo'}
                  className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal" />
              ))}
              {tpl.requiere_firma && <div className="text-[11px] text-sub">El paciente deberá firmar este documento.</div>}
            </div>
          ) : (
            <textarea value={f.contenido} onChange={(e) => setF((p) => ({ ...p, contenido: e.target.value }))} placeholder="Contenido (opcional)" rows={4}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
          )}
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !f.titulo.trim()} className="w-full">{saving ? 'Guardando…' : 'Emitir documento'}</Button>
        </BottomSheet>
      )}

      {gestor && <PlantillasManager plantillas={plantillas} onClose={() => setGestor(false)} onChanged={loadTpl} />}
    </div>
  );
}

function PlantillasManager({ plantillas, onClose, onChanged }: { plantillas: PlantillaDoc[]; onClose: () => void; onChanged: () => void }) {
  const [nombre, setNombre] = useState('');
  const [tipo, setTipo] = useState('consentimiento');
  const [firma, setFirma] = useState(true);
  const [bloques, setBloques] = useState<BloqueDoc[]>([{ tipo: 'parrafo', texto: '' }]);
  const [saving, setSaving] = useState(false);

  const setBloque = (i: number, patch: Partial<BloqueDoc>) => setBloques((bs) => bs.map((b, j) => (j === i ? { ...b, ...patch } : b)));

  const crear = async () => {
    setSaving(true);
    try {
      await api.medico.crearPlantillaDoc({
        nombre: nombre.trim(), tipo, requiere_firma: firma,
        bloques: bloques.filter((b) => (b.tipo === 'parrafo' ? (b.texto || '').trim() : (b.label || '').trim())),
      });
      setNombre(''); setBloques([{ tipo: 'parrafo', texto: '' }]); onChanged();
    } finally { setSaving(false); }
  };
  const eliminar = async (id: string) => { await api.medico.eliminarPlantillaDoc(id); onChanged(); };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Plantillas de documento</div>
      {plantillas.map((t) => (
        <div key={t.id} className="flex items-center justify-between rounded-xl bg-[#F6FBF9] px-3 py-2">
          <span className="text-[13px] text-ink">{t.nombre}{t.requiere_firma ? ' · firma' : ''}</span>
          <button onClick={() => eliminar(t.id)} className="text-[11px] font-semibold text-danger">Quitar</button>
        </div>
      ))}
      <div className="text-[12px] font-semibold text-ink mt-2">Nueva plantilla</div>
      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Consentimiento extracción)"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal" />
      <div className="flex gap-2 items-center">
        <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
          <option value="consentimiento">Consentimiento</option>
          <option value="certificado">Certificado</option>
          <option value="otro">Otro</option>
        </select>
        <label className="flex items-center gap-1.5 text-[12px] text-ink"><input type="checkbox" checked={firma} onChange={(e) => setFirma(e.target.checked)} className="w-4 h-4 accent-teal" />Requiere firma</label>
      </div>
      {bloques.map((b, i) => (
        <div key={i} className="flex gap-1.5 items-center">
          <select value={b.tipo} onChange={(e) => setBloque(i, { tipo: e.target.value })} className="rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12px] text-ink outline-none focus:border-teal">
            <option value="parrafo">Párrafo</option>
            <option value="campo">Campo</option>
          </select>
          {b.tipo === 'parrafo'
            ? <input value={b.texto || ''} onChange={(e) => setBloque(i, { texto: e.target.value })} placeholder="Texto fijo" className="flex-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-[13px] text-ink outline-none focus:border-teal" />
            : <input value={b.label || ''} onChange={(e) => setBloque(i, { label: e.target.value, clave: e.target.value })} placeholder="Etiqueta del campo" className="flex-1 rounded-lg border-[1.5px] border-border-strong bg-white px-2.5 py-2 text-[13px] text-ink outline-none focus:border-teal" />}
        </div>
      ))}
      <button onClick={() => setBloques((bs) => [...bs, { tipo: 'parrafo', texto: '' }])} className="text-[12.5px] font-semibold text-teal-dark self-start">+ Agregar bloque</button>
      <Button onClick={crear} disabled={saving || !nombre.trim()} className="w-full">{saving ? 'Guardando…' : 'Crear plantilla'}</Button>
    </BottomSheet>
  );
}

// ─────────────────────── Periodontograma completo (70.5) ───────────────────────
const FDI_SUP = ['1.8', '1.7', '1.6', '1.5', '1.4', '1.3', '1.2', '1.1', '2.1', '2.2', '2.3', '2.4', '2.5', '2.6', '2.7', '2.8'];
const FDI_INF = ['4.8', '4.7', '4.6', '4.5', '4.4', '4.3', '4.2', '4.1', '3.1', '3.2', '3.3', '3.4', '3.5', '3.6', '3.7', '3.8'];
const PERIO_SITIOS = ['mv', 'v', 'dv', 'mp', 'p', 'dp'];
const SITIO_LABEL: Record<string, string> = { mv: 'MV', v: 'V', dv: 'DV', mp: 'MP', p: 'P', dp: 'DP' };
const psColor = (ps?: number) => (ps == null ? 'bg-[#F2F6F5] text-sub' : ps >= 6 ? 'bg-[#F6D9CF] text-danger' : ps >= 4 ? 'bg-warn-bg text-warn' : 'bg-teal-soft text-teal-dark');

function maxPs(p?: PerioPieza): number | undefined {
  const vals = [p?.ps, ...Object.values(p?.sitios ?? {}).map((s) => s.ps)].filter((v): v is number => v != null);
  return vals.length ? Math.max(...vals) : undefined;
}
function tieneSangrado(p?: PerioPieza): boolean {
  return !!p?.sangrado || Object.values(p?.sitios ?? {}).some((s) => s.sangrado);
}

export function PeriodontogramaSection({ patientId }: { patientId: string }) {
  const [datos, setDatos] = useState<PerioDatos>({});
  const [anteriores, setAnteriores] = useState(0);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    api.medico.periodontograma(patientId).then((p) => {
      setDatos(p?.datos ?? {});
      setAnteriores(p ? p.tomas_anteriores + 1 : 0);
      setDirty(false);
    });
  }, [patientId]);

  const guardar = async () => {
    setSaving(true);
    try { const p = await api.medico.guardarPeriodontograma(patientId, datos); setAnteriores(p.tomas_anteriores + 1); setDatos(p.datos); setDirty(false); }
    finally { setSaving(false); }
  };

  const Diente = ({ t }: { t: string }) => {
    const p = datos[t];
    const ps = maxPs(p);
    return (
      <button onClick={() => setSel(t)} className={`relative aspect-square rounded-md border border-border-strong text-[10px] font-bold tabular-nums flex items-center justify-center ${psColor(ps)}`}>
        {ps ?? ''}
        {tieneSangrado(p) && <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-danger" />}
        {p?.movilidad ? <span className="absolute bottom-0 left-0.5 text-[7px] text-sub">M{p.movilidad}</span> : null}
      </button>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Periodontograma</div>
        {anteriores > 0 && <span className="text-[11px] text-sub">{anteriores} toma{anteriores === 1 ? '' : 's'}</span>}
      </div>
      <div className="text-[11.5px] text-sub mb-2">Toca un diente para registrar sondaje por sitio, recesión, sangrado, movilidad y furca.</div>
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

      {sel && (
        <PerioPiezaEditor
          num={sel} pieza={datos[sel]}
          onClose={() => setSel(null)}
          onSave={(p) => { setDatos((prev) => { const n = { ...prev }; if (p) n[sel] = p; else delete n[sel]; return n; }); setDirty(true); setSel(null); }}
        />
      )}
    </div>
  );
}

function PerioPiezaEditor({ num, pieza, onClose, onSave }: {
  num: string; pieza?: PerioPieza; onClose: () => void; onSave: (p: PerioPieza | null) => void;
}) {
  const [sitios, setSitios] = useState<Record<string, PerioSitio>>(() => ({ ...(pieza?.sitios ?? {}) }));
  const [movilidad, setMovilidad] = useState(pieza?.movilidad != null ? String(pieza.movilidad) : '');
  const [furca, setFurca] = useState(pieza?.furca != null ? String(pieza.furca) : '');

  const setSitio = (s: string, campo: 'ps' | 'rec', val: string) => {
    setSitios((prev) => {
      const cur = { ...(prev[s] ?? {}) };
      if (val === '') delete cur[campo]; else cur[campo] = Number(val);
      return { ...prev, [s]: cur };
    });
  };
  const toggleSangrado = (s: string) => setSitios((prev) => ({ ...prev, [s]: { ...(prev[s] ?? {}), sangrado: !prev[s]?.sangrado } }));

  const guardar = () => {
    const outSitios: Record<string, PerioSitio> = {};
    for (const s of PERIO_SITIOS) {
      const v = sitios[s] ?? {};
      const e: PerioSitio = {};
      if (v.ps != null) e.ps = v.ps;
      if (v.rec != null) e.rec = v.rec;
      if (v.sangrado) e.sangrado = true;
      if (Object.keys(e).length) outSitios[s] = e;
    }
    const out: PerioPieza = {};
    if (Object.keys(outSitios).length) out.sitios = outSitios;
    if (movilidad !== '') out.movilidad = Number(movilidad);
    if (furca !== '') out.furca = Number(furca);
    onSave(Object.keys(out).length ? out : null);
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Pieza {num}</div>
      <div className="flex gap-2">
        <div className="flex-1">
          <div className="text-[11px] text-sub mb-1">Movilidad (0–3)</div>
          <select value={movilidad} onChange={(e) => setMovilidad(e.target.value)} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
            <option value="">—</option>{[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="flex-1">
          <div className="text-[11px] text-sub mb-1">Furca (0–3)</div>
          <select value={furca} onChange={(e) => setFurca(e.target.value)} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
            <option value="">—</option>{[0, 1, 2, 3].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
      </div>

      <div className="text-[12px] font-semibold text-ink mt-1">Sitios · PS / Recesión (mm) · sangrado</div>
      <div className="flex flex-col gap-1.5">
        {PERIO_SITIOS.map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div className="w-9 text-[11.5px] font-semibold text-teal-dark">{SITIO_LABEL[s]}</div>
            <input inputMode="numeric" value={sitios[s]?.ps ?? ''} onChange={(e) => setSitio(s, 'ps', e.target.value)} placeholder="PS"
              className="w-14 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-1.5 text-[13px] text-ink text-center outline-none focus:border-teal" />
            <input inputMode="numeric" value={sitios[s]?.rec ?? ''} onChange={(e) => setSitio(s, 'rec', e.target.value)} placeholder="Rec"
              className="w-14 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-1.5 text-[13px] text-ink text-center outline-none focus:border-teal" />
            <button onClick={() => toggleSangrado(s)} className={`ml-auto rounded-full px-3 py-1.5 text-[11px] font-semibold border ${sitios[s]?.sangrado ? 'bg-danger text-white border-danger' : 'bg-white text-sub border-border'}`}>
              Sangrado
            </button>
          </div>
        ))}
      </div>
      <Button onClick={guardar} className="w-full">Aplicar pieza {num}</Button>
    </BottomSheet>
  );
}

// ─────────────────────── Diagnóstico CIE-10 (71.20) ───────────────────────
export function DiagnosticosSection({ patientId }: { patientId: string }) {
  const [lista, setLista] = useState<Diagnostico[]>([]);
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [hits, setHits] = useState<Cie10Item[]>([]);
  const [sel, setSel] = useState<Cie10Item | null>(null);
  const [tipo, setTipo] = useState('principal');
  const [obs, setObs] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.medico.diagnosticos(patientId).then(setLista).catch(() => setLista([]));
  useEffect(() => { load(); }, [patientId]);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      if (q.trim().length < 2) { setHits([]); return; }
      api.medico.buscarCie10(q.trim()).then(setHits).catch(() => setHits([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, open]);

  const abrir = () => { setOpen(true); setQ(''); setHits([]); setSel(null); setTipo('principal'); setObs(''); setError(null); };
  const guardar = async () => {
    if (!sel) return;
    setSaving(true); setError(null);
    try {
      await api.medico.agregarDiagnostico(patientId, { codigo: sel.codigo, tipo, observacion: obs || undefined });
      setOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo agregar el diagnóstico.');
    } finally { setSaving(false); }
  };
  const quitar = async (id: string) => { await api.medico.quitarDiagnostico(id); await load(); };

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="font-heading font-bold text-[13px] text-ink">Diagnósticos (CIE-10)</div>
        <button onClick={abrir} className="text-[12px] font-semibold text-teal-dark">+ Agregar</button>
      </div>
      {lista.length === 0 ? (
        <div className="text-sm text-sub">Sin diagnósticos registrados.</div>
      ) : (
        <div className="flex flex-col gap-2">
          {lista.map((d) => (
            <div key={d.id} className="bg-white border border-border rounded-2xl px-3.5 py-3">
              <div className="flex items-center gap-2">
                <span className="font-heading font-bold text-[11px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark tabular-nums">{d.codigo}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${d.tipo === 'principal' ? 'bg-[#EEF6FF] text-[#1E5AA8]' : 'bg-[#F1F1F1] text-sub'}`}>{d.tipo}</span>
                <button onClick={() => quitar(d.id)} className="ml-auto text-[11px] font-semibold text-danger">Quitar</button>
              </div>
              <div className="mt-1 text-[13px] text-ink">{d.descripcion}</div>
              {d.observacion && <div className="mt-0.5 text-[11.5px] text-sub">{d.observacion}</div>}
            </div>
          ))}
        </div>
      )}

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Agregar diagnóstico</div>
          {!sel ? (
            <>
              <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por código o descripción (ej. caries, K02)"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <div className="max-h-[45vh] overflow-y-auto scrollhide flex flex-col gap-1.5">
                {q.trim().length < 2 && <div className="text-[12px] text-sub">Escribe al menos 2 caracteres.</div>}
                {hits.map((h) => (
                  <button key={h.id} onClick={() => setSel(h)} className="text-left rounded-xl bg-[#F6FBF9] px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-heading font-bold text-[11px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark tabular-nums">{h.codigo}</span>
                      <span className="text-[13px] text-ink">{h.descripcion}</span>
                    </div>
                    {h.categoria && <div className="mt-0.5 text-[10.5px] text-sub">{h.categoria}</div>}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="rounded-xl bg-[#F6FBF9] px-3 py-2.5 flex items-center gap-2">
                <span className="font-heading font-bold text-[11px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark tabular-nums">{sel.codigo}</span>
                <span className="text-[13px] text-ink flex-1">{sel.descripcion}</span>
                <button onClick={() => setSel(null)} className="text-[11px] font-semibold text-teal-dark">Cambiar</button>
              </div>
              <select value={tipo} onChange={(e) => setTipo(e.target.value)}
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
                <option value="principal">Diagnóstico principal</option>
                <option value="secundario">Diagnóstico secundario</option>
              </select>
              <input value={obs} onChange={(e) => setObs(e.target.value)} placeholder="Observación (opcional)"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              {error && <div className="text-xs text-danger">{error}</div>}
              <Button onClick={guardar} disabled={saving} className="w-full">{saving ? 'Guardando…' : 'Agregar diagnóstico'}</Button>
            </>
          )}
        </BottomSheet>
      )}
    </div>
  );
}

// ─────────────────────── Odontograma con caras y dx/tx (70.11) ───────────────────────
const CARAS_ORDEN = ['V', 'O', 'L', 'M', 'D'];
// Dentición permanente FDI, en dos filas visuales (superior / inferior).
const FILA_SUP = ['18', '17', '16', '15', '14', '13', '12', '11', '21', '22', '23', '24', '25', '26', '27', '28'];
const FILA_INF = ['48', '47', '46', '45', '44', '43', '42', '41', '31', '32', '33', '34', '35', '36', '37', '38'];

function piezaMarcada(p?: OdontogramaPieza): { dx: boolean; tx: boolean; ausente: boolean } {
  const caras = p?.caras ?? {};
  const dx = Object.values(caras).some((c) => c.dx) || (!!p?.pieza && ['ausente', 'extraccion_indicada', 'resto_radicular'].includes(p.pieza));
  const tx = Object.values(caras).some((c) => c.tx) || (!!p?.pieza && ['corona', 'implante', 'endodoncia'].includes(p.pieza));
  return { dx, tx, ausente: p?.pieza === 'ausente' };
}

export function OdontogramaSection({ patientId, initial }: { patientId: string; initial: OdontogramaPiezas }) {
  const [piezas, setPiezas] = useState<OdontogramaPiezas>(initial || {});
  const [cat, setCat] = useState<OdontogramaCatalogo | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => { api.medico.odontogramaCatalogo().then(setCat).catch(() => setCat(null)); }, []);

  const guardar = async (next: OdontogramaPiezas) => {
    setPiezas(next);
    try { const r = await api.medico.odontograma(patientId, next); setPiezas(r.piezas); } catch { /* se mantiene el optimista */ }
  };

  const Diente = ({ num }: { num: string }) => {
    const m = piezaMarcada(piezas[num]);
    return (
      <button onClick={() => setSel(num)} className={`relative aspect-square rounded-md border text-[9px] font-semibold tabular-nums grid place-items-center
        ${m.ausente ? 'bg-[#F2F6F5] text-sub border-border line-through' : m.tx ? 'bg-teal-soft border-teal text-teal-dark' : m.dx ? 'bg-[#FBE4DC] border-[#E0A292] text-[#9C3B22]' : 'bg-white border-border-strong text-sub'}`}>
        {num}
        {(m.dx || m.tx) && !m.ausente && (
          <span className="absolute bottom-0.5 flex gap-0.5">
            {m.dx && <span className="w-1 h-1 rounded-full bg-[#C0392B]" />}
            {m.tx && <span className="w-1 h-1 rounded-full bg-teal" />}
          </span>
        )}
      </button>
    );
  };

  return (
    <div>
      <div className="font-heading font-bold text-[13px] text-ink mb-1">Odontograma</div>
      <div className="text-[11.5px] text-sub mb-2">Toca una pieza para marcar caras, diagnósticos y tratamientos.</div>
      <div className="bg-white border border-border rounded-2xl p-3 flex flex-col gap-1.5">
        <div className="grid grid-cols-8 gap-1">{FILA_SUP.map((n) => <Diente key={n} num={n} />)}</div>
        <div className="grid grid-cols-8 gap-1">{FILA_INF.map((n) => <Diente key={n} num={n} />)}</div>
        <div className="flex items-center gap-3 pt-1.5 text-[10px] text-sub">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#C0392B]" /> Diagnóstico</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-teal" /> Tratamiento</span>
        </div>
      </div>

      {sel && cat && (
        <PiezaEditor
          num={sel} cat={cat} pieza={piezas[sel]}
          onClose={() => setSel(null)}
          onSave={(p) => { const next = { ...piezas }; if (p) next[sel] = p; else delete next[sel]; guardar(next); setSel(null); }}
        />
      )}
    </div>
  );
}

function PiezaEditor({ num, cat, pieza, onClose, onSave }: {
  num: string; cat: OdontogramaCatalogo; pieza?: OdontogramaPieza;
  onClose: () => void; onSave: (p: OdontogramaPieza | null) => void;
}) {
  const [piezaEstado, setPiezaEstado] = useState(pieza?.pieza ?? '');
  const [caras, setCaras] = useState<Record<string, { dx: string; tx: string; tx_estado: string }>>(() => {
    const base: Record<string, { dx: string; tx: string; tx_estado: string }> = {};
    for (const c of CARAS_ORDEN) {
      const m = pieza?.caras?.[c];
      base[c] = { dx: m?.dx ?? '', tx: m?.tx ?? '', tx_estado: m?.tx_estado ?? '' };
    }
    return base;
  });
  const caraLabel = (c: string) => cat.caras.find((x) => x.codigo === c)?.label ?? c;

  const guardar = () => {
    const outCaras: Record<string, { dx?: string; tx?: string; tx_estado?: string }> = {};
    for (const c of CARAS_ORDEN) {
      const m = caras[c];
      const e: { dx?: string; tx?: string; tx_estado?: string } = {};
      if (m.dx) e.dx = m.dx;
      if (m.tx) { e.tx = m.tx; if (m.tx_estado) e.tx_estado = m.tx_estado; }
      if (Object.keys(e).length) outCaras[c] = e;
    }
    const out: OdontogramaPieza = {};
    if (piezaEstado) out.pieza = piezaEstado;
    if (Object.keys(outCaras).length) out.caras = outCaras;
    onSave(Object.keys(out).length ? out : null);
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Pieza {num}</div>

      <div>
        <div className="text-[12px] font-semibold text-ink mb-1">Estado de la pieza</div>
        <select value={piezaEstado} onChange={(e) => setPiezaEstado(e.target.value)}
          className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
          <option value="">— sin marca —</option>
          {cat.pieza_estados.map((m) => <option key={m.codigo} value={m.codigo}>{m.label}</option>)}
        </select>
      </div>

      <div className="text-[12px] font-semibold text-ink mt-1">Caras</div>
      <div className="flex flex-col gap-2 max-h-[45vh] overflow-y-auto scrollhide">
        {CARAS_ORDEN.map((c) => (
          <div key={c} className="rounded-xl border border-border p-2.5">
            <div className="text-[11.5px] font-semibold text-teal-dark mb-1.5">{caraLabel(c)}</div>
            <div className="flex gap-1.5">
              <select value={caras[c].dx} onChange={(e) => setCaras((p) => ({ ...p, [c]: { ...p[c], dx: e.target.value } }))}
                className="flex-1 min-w-0 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12px] text-ink outline-none focus:border-teal">
                <option value="">Diagnóstico…</option>
                {cat.diagnosticos.map((m) => <option key={m.codigo} value={m.codigo}>{m.label}</option>)}
              </select>
              <select value={caras[c].tx} onChange={(e) => setCaras((p) => ({ ...p, [c]: { ...p[c], tx: e.target.value, tx_estado: e.target.value ? (p[c].tx_estado || 'planificado') : '' } }))}
                className="flex-1 min-w-0 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12px] text-ink outline-none focus:border-teal">
                <option value="">Tratamiento…</option>
                {cat.tratamientos.map((m) => <option key={m.codigo} value={m.codigo}>{m.label}</option>)}
              </select>
              {caras[c].tx && (
                <select value={caras[c].tx_estado} onChange={(e) => setCaras((p) => ({ ...p, [c]: { ...p[c], tx_estado: e.target.value } }))}
                  className="w-24 shrink-0 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12px] text-ink outline-none focus:border-teal">
                  {cat.tx_estados.map((m) => <option key={m.codigo} value={m.codigo}>{m.label}</option>)}
                </select>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button onClick={guardar} className="w-full">Guardar pieza {num}</Button>
    </BottomSheet>
  );
}
