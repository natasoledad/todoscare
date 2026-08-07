import { useEffect, useState } from 'react';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { PlanItem, PlanTratamiento, SignosVitales } from '../../api/types';

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
