import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { CrmAtribucion, CrmCampanas } from '../../api/types';
import { money } from './DetalleClinicaView';

const CANALES: { id: string; label: string; icon: string }[] = [
  { id: 'google_ads', label: 'Google Ads', icon: '🔍' },
  { id: 'meta_ads', label: 'Meta Ads', icon: '📘' },
  { id: 'instagram', label: 'Instagram', icon: '📸' },
  { id: 'email', label: 'Email', icon: '✉️' },
  { id: 'whatsapp', label: 'WhatsApp', icon: '💬' },
  { id: 'seo', label: 'SEO', icon: '🌐' },
  { id: 'referidos', label: 'Referidos', icon: '🤝' },
];
const canalMeta = (id: string) => CANALES.find((c) => c.id === id) ?? { label: id, icon: '📣' };

/** Gestión de marketing digital del CRM — compartida por Admin (por clínica)
 *  y Empresa (su propia clínica). El gasto de cada campaña alimenta el CAC. */
export function Campanas({ clinicId, backTo }: { clinicId?: string; backTo: string }) {
  const navigate = useNavigate();
  const [data, setData] = useState<CrmCampanas | null>(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ nombre: '', canal: 'google_ads', presupuesto: '', gasto: '', leads: '', conversiones: '' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [atrib, setAtrib] = useState<CrmAtribucion | null>(null);

  const load = () => api.crm.campanas(clinicId).then(setData);
  useEffect(() => { load(); }, [clinicId]);

  const crear = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.crm.crearCampana({
        clinic_id: clinicId,
        nombre: f.nombre.trim(),
        canal: f.canal,
        presupuesto: Number(f.presupuesto) || 0,
        gasto: Number(f.gasto) || 0,
        leads: Number(f.leads) || 0,
        conversiones: Number(f.conversiones) || 0,
      });
      setOpen(false);
      setF({ nombre: '', canal: 'google_ads', presupuesto: '', gasto: '', leads: '', conversiones: '' });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la campaña');
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (id: string, estado: string) => {
    await api.crm.actualizarCampana(id, { estado: estado === 'activa' ? 'pausada' : 'activa' });
    await load();
  };
  const baja = async (id: string) => { await api.crm.eliminarCampana(id); await load(); };

  const r = data?.resumen;
  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Marketing digital" onBack={() => navigate(backTo)} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-3">
        {/* Resumen */}
        <div className="grid grid-cols-2 gap-2">
          <Tile label="Campañas activas" value={r ? `${r.activas}/${r.campanas}` : '—'} />
          <Tile label="Inversión" value={r ? money(r.inversion) : '—'} />
          <Tile label="Leads → conv. reales" value={r ? `${r.leads} → ${r.conversiones_reales}` : '—'} />
          <Tile label="CAC real promedio" value={r?.cac_real_promedio == null ? '—' : money(r.cac_real_promedio)} tone="good" />
        </div>
        <div className="px-1 text-[11px] text-sub">
          El gasto de cada campaña se asienta en el ledger; las conversiones reales son pacientes atribuidos.
        </div>

        {data && data.items.length === 0 && <div className="text-center text-sm text-sub py-8">Sin campañas todavía.</div>}
        {data?.items.map((c) => {
          const meta = canalMeta(c.canal);
          const usado = c.presupuesto_usado ?? 0;
          return (
            <div key={c.id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">{meta.icon}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[14px] text-ink truncate">{c.nombre}</div>
                  <div className="text-xs text-sub">{meta.label}</div>
                </div>
                <StatusTag label={c.estado === 'activa' ? 'Activa' : c.estado === 'pausada' ? 'Pausada' : 'Finalizada'} tone={c.estado === 'activa' ? 'teal' : 'warn'} />
              </div>
              {/* barra presupuesto usado */}
              <div className="mt-2.5 h-1.5 rounded-full bg-[#EDF3F1] overflow-hidden">
                <div className="h-full bg-teal" style={{ width: `${Math.min(100, Math.round(usado * 100))}%` }} />
              </div>
              <div className="mt-1 flex justify-between text-[11px] text-sub">
                <span>{money(c.gasto)} / {money(c.presupuesto)}</span>
                <span>{c.leads} leads · <strong className="text-teal-dark">{c.conversiones_reales} reales</strong> · CAC {c.cac_real == null ? '—' : money(c.cac_real)}</span>
              </div>
              <div className="mt-3 flex gap-2">
                <Button onClick={() => toggle(c.id, c.estado)} variant="outline" className="text-[12.5px] py-2 px-3.5">{c.estado === 'activa' ? 'Pausar' : 'Activar'}</Button>
                <Button onClick={() => api.crm.atribucion(c.id).then(setAtrib)} variant="ghost" className="text-[12.5px] py-2 px-3.5">Atribución</Button>
                <Button onClick={() => baja(c.id)} variant="ghost" className="text-[12.5px] py-2 px-3.5">Eliminar</Button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => { setOpen(true); setError(null); }} className="w-full">+ Nueva campaña</Button>
      </div>

      {atrib && (
        <BottomSheet onClose={() => setAtrib(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Atribución · {atrib.nombre}</div>
          <div className="text-[12.5px] text-sub">Pacientes que llegaron por esta campaña y los ingresos que generaron.</div>
          <div className="grid grid-cols-2 gap-2">
            <Tile label="Conversiones reales" value={String(atrib.conversiones_reales)} />
            <Tile label="Ingresos atribuidos" value={money(atrib.ingresos_atribuidos)} />
            <Tile label="CAC real" value={atrib.cac_real == null ? '—' : money(atrib.cac_real)} />
            <Tile label="ROAS real" value={atrib.roas_real == null ? '—' : `${atrib.roas_real}×`} tone="good" />
          </div>
          <div className="rounded-xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12.5px] text-teal-dark">
            ROI {atrib.roi_real == null ? '—' : `${(atrib.roi_real * 100).toFixed(0)}%`} · embudo: {atrib.leads} leads → {atrib.conversiones_reales} pacientes → {money(atrib.ingresos_atribuidos)} en ingresos.
          </div>
          {atrib.pacientes.length > 0 && (
            <div>
              <div className="text-[12px] font-semibold text-ink pb-1">Pacientes atribuidos</div>
              {atrib.pacientes.map((n, i) => <div key={i} className="text-[13px] text-sub">• {n}</div>)}
            </div>
          )}
          <Button onClick={() => setAtrib(null)} variant="ghost" className="w-full">Cerrar</Button>
        </BottomSheet>
      )}

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva campaña</div>
          <input value={f.nombre} onChange={(e) => setF((p) => ({ ...p, nombre: e.target.value }))} placeholder="Nombre de la campaña"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <select value={f.canal} onChange={(e) => setF((p) => ({ ...p, canal: e.target.value }))}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            {CANALES.map((c) => <option key={c.id} value={c.id}>{c.icon} {c.label}</option>)}
          </select>
          <div className="flex gap-2">
            <input value={f.presupuesto} onChange={(e) => setF((p) => ({ ...p, presupuesto: e.target.value }))} placeholder="Presupuesto" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={f.gasto} onChange={(e) => setF((p) => ({ ...p, gasto: e.target.value }))} placeholder="Gasto inicial" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <div className="flex gap-2">
            <input value={f.leads} onChange={(e) => setF((p) => ({ ...p, leads: e.target.value }))} placeholder="Leads" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={f.conversiones} onChange={(e) => setF((p) => ({ ...p, conversiones: e.target.value }))} placeholder="Conversiones" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !f.nombre} className="w-full">{saving ? 'Creando…' : 'Crear campaña'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: 'good' }) {
  return (
    <div className="rounded-2xl border border-border bg-white px-3.5 py-3">
      <div className="text-[11px] text-sub">{label}</div>
      <div className={`mt-0.5 font-heading font-extrabold text-[18px] tabular-nums ${tone === 'good' ? 'text-teal-dark' : 'text-ink'}`}>{value}</div>
    </div>
  );
}
