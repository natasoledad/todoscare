import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { PlanAdmin, TycAdmin } from '../../api/types';

const TIPO_LABEL: Record<string, string> = { individual: 'Individual', empresa: 'Empresa', publico: 'Público' };

export function Config() {
  const navigate = useNavigate();
  const { me } = useAuth();
  const isSuper = me?.roles.includes('super_admin') ?? false;
  const [planes, setPlanes] = useState<PlanAdmin[]>([]);
  const [tyc, setTyc] = useState<TycAdmin[]>([]);
  const [planOpen, setPlanOpen] = useState(false);
  const [tycOpen, setTycOpen] = useState(false);
  const [plan, setPlan] = useState({ tipo: 'individual', esfera: '', nombre: '', precio: '' });
  const [tycF, setTycF] = useState({ pais: 'MX', version: '', contenido: '' });
  const [error, setError] = useState<string | null>(null);

  const load = () => Promise.all([api.admin.planes(), api.admin.tyc()]).then(([p, t]) => { setPlanes(p); setTyc(t); });
  useEffect(() => { load(); }, []);

  const crearPlan = async () => {
    setError(null);
    try {
      await api.admin.crearPlan({ tipo: plan.tipo, esfera: plan.tipo === 'publico' ? plan.esfera : undefined, nombre: plan.nombre, precio: Number(plan.precio) });
      setPlanOpen(false);
      setPlan({ tipo: 'individual', esfera: '', nombre: '', precio: '' });
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'Error'); }
  };

  const publicarTyc = async () => {
    setError(null);
    try {
      await api.admin.publicarTyc(tycF);
      setTycOpen(false);
      setTycF({ pais: 'MX', version: '', contenido: '' });
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'Error'); }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Configuración global" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-8 flex flex-col gap-3">
        {/* Planes */}
        <div className="flex items-center justify-between">
          <div className="font-heading font-bold text-[13px] text-ink">Planes</div>
          {isSuper && <button onClick={() => setPlanOpen(true)} className="text-[13px] font-heading font-bold text-teal cursor-pointer">+ Nuevo</button>}
        </div>
        {planes.length === 0 && <div className="text-sm text-sub">Sin planes configurados.</div>}
        {planes.map((p) => (
          <div key={p.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[13.5px] text-ink">{p.nombre}</div>
              <div className="text-xs text-sub">{TIPO_LABEL[p.tipo]}{p.esfera ? ` · ${p.esfera}` : ''}</div>
            </div>
            <div className="font-heading font-bold text-sm text-ink tabular-nums">${p.precio}</div>
          </div>
        ))}

        {/* T&C */}
        <div className="flex items-center justify-between pt-3">
          <div className="font-heading font-bold text-[13px] text-ink">Términos y condiciones por país</div>
          {isSuper && <button onClick={() => setTycOpen(true)} className="text-[13px] font-heading font-bold text-teal cursor-pointer">+ Publicar</button>}
        </div>
        {tyc.map((t) => (
          <div key={t.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[13.5px] text-ink">{t.pais} · v{t.version}</div>
              <div className="text-xs text-sub">Publicado {new Date(t.publicado_en).toLocaleDateString('es-MX')}</div>
            </div>
          </div>
        ))}
        <div className="text-[11.5px] text-sub">Publicar una versión nueva obliga a los pacientes de ese país a re-aceptar en su próximo ingreso.</div>
      </div>

      {planOpen && (
        <BottomSheet onClose={() => setPlanOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo plan</div>
          <select value={plan.tipo} onChange={(e) => setPlan((p) => ({ ...p, tipo: e.target.value }))}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="individual">Individual</option><option value="empresa">Empresa</option><option value="publico">Público</option>
          </select>
          {plan.tipo === 'publico' && (
            <select value={plan.esfera} onChange={(e) => setPlan((p) => ({ ...p, esfera: e.target.value }))}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="">Esfera…</option><option value="federal">Federal</option><option value="estatal">Estatal</option><option value="municipal">Municipal</option>
            </select>
          )}
          <input value={plan.nombre} onChange={(e) => setPlan((p) => ({ ...p, nombre: e.target.value }))} placeholder="Nombre del plan"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={plan.precio} onChange={(e) => setPlan((p) => ({ ...p, precio: e.target.value }))} placeholder="Precio" inputMode="numeric"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crearPlan} disabled={!plan.nombre || !plan.precio} className="w-full">Crear plan</Button>
        </BottomSheet>
      )}

      {tycOpen && (
        <BottomSheet onClose={() => setTycOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Publicar T&C</div>
          <div className="flex gap-2">
            <select value={tycF.pais} onChange={(e) => setTycF((p) => ({ ...p, pais: e.target.value }))}
              className="w-24 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="MX">MX</option><option value="CL">CL</option><option value="CO">CO</option><option value="BR">BR</option>
            </select>
            <input value={tycF.version} onChange={(e) => setTycF((p) => ({ ...p, version: e.target.value }))} placeholder="Versión (ej. 2.0)"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <textarea value={tycF.contenido} onChange={(e) => setTycF((p) => ({ ...p, contenido: e.target.value }))} placeholder="Contenido de los términos…" rows={4}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={publicarTyc} disabled={!tycF.version || !tycF.contenido} className="w-full">Publicar (bloqueante para pacientes)</Button>
        </BottomSheet>
      )}
    </div>
  );
}
