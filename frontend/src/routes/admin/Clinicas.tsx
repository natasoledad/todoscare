import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { ClinicAdmin } from '../../api/types';

export function Clinicas() {
  const navigate = useNavigate();
  const { primaryRole, me } = useAuth();
  const isSuper = me?.roles.includes('super_admin') ?? false;
  const [clinicas, setClinicas] = useState<ClinicAdmin[]>([]);
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState<ClinicAdmin | null>(null);
  const [f, setF] = useState({ razon_social: '', pais: 'MX', responsable_sanitario: '', sucursal_nombre: '', admin_nombre: '', admin_correo: '', admin_password: '' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.admin.clinicas().then(setClinicas);
  useEffect(() => { load(); }, []);

  const set = (k: keyof typeof f, v: string) => setF((p) => ({ ...p, [k]: v }));

  const crear = async () => {
    setError(null);
    setSaving(true);
    try {
      await api.admin.altaClinica(f);
      setOpen(false);
      setF({ razon_social: '', pais: 'MX', responsable_sanitario: '', sucursal_nombre: '', admin_nombre: '', admin_correo: '', admin_password: '' });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la clínica');
    } finally {
      setSaving(false);
    }
  };

  const darDeBaja = async () => {
    if (!confirm) return;
    await api.admin.bajaClinica(confirm.id);
    setConfirm(null);
    await load();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Clínicas y sucursales" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {clinicas.map((c) => (
          <div key={c.id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{c.razon_social}</div>
                <div className="mt-0.5 text-xs text-sub">{c.pais} · {c.sucursales} sucursal(es) · {c.pacientes} paciente(s)</div>
              </div>
              <StatusTag label={c.activo ? 'Activa' : 'Baja'} tone={c.activo ? 'teal' : 'warn'} />
            </div>
            {isSuper && c.activo && (
              <div className="mt-3">
                <Button onClick={() => setConfirm(c)} variant="outline" className="text-[13px] py-2.5 px-4">Dar de baja</Button>
              </div>
            )}
          </div>
        ))}
      </div>
      {isSuper && (
        <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
          <Button onClick={() => setOpen(true)} className="w-full">+ Alta de clínica (nuevo tenant)</Button>
        </div>
      )}
      {!isSuper && (
        <div className="px-5 pb-6 text-center text-xs text-sub">
          Como admin de clínica ({primaryRole}) solo ves tu propia clínica. El alta de nuevos tenants es del Super-Admin.
        </div>
      )}

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Alta de clínica (nuevo tenant)</div>
          <input value={f.razon_social} onChange={(e) => set('razon_social', e.target.value)} placeholder="Razón social"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <select value={f.pais} onChange={(e) => set('pais', e.target.value)}
              className="w-24 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="MX">MX</option><option value="CL">CL</option><option value="CO">CO</option><option value="BR">BR</option>
            </select>
            <input value={f.responsable_sanitario} onChange={(e) => set('responsable_sanitario', e.target.value)} placeholder="Responsable sanitario"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <input value={f.sucursal_nombre} onChange={(e) => set('sucursal_nombre', e.target.value)} placeholder="Primera sucursal"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="font-heading font-semibold text-xs text-sub pt-1">Admin de la clínica inicial</div>
          <input value={f.admin_nombre} onChange={(e) => set('admin_nombre', e.target.value)} placeholder="Nombre del admin"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={f.admin_correo} onChange={(e) => set('admin_correo', e.target.value)} placeholder="correo del admin"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input type="password" value={f.admin_password} onChange={(e) => set('admin_password', e.target.value)} placeholder="Contraseña (mín. 8)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !f.razon_social || !f.sucursal_nombre || !f.admin_correo || !f.admin_password} className="w-full">
            {saving ? 'Creando tenant…' : 'Crear y activar tenant'}
          </Button>
        </BottomSheet>
      )}

      {confirm && (
        <BottomSheet onClose={() => setConfirm(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">¿Dar de baja "{confirm.razon_social}"?</div>
          <div className="text-[13px] leading-relaxed text-sub">
            Es una baja lógica: la clínica deja de operar pero se conserva su histórico para auditoría. Esta acción
            requiere confirmación.
          </div>
          <Button onClick={darDeBaja} className="w-full" style={{ background: 'var(--color-danger)' }}>Sí, dar de baja</Button>
          <Button onClick={() => setConfirm(null)} variant="ghost" className="w-full">Cancelar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
