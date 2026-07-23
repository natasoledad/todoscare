import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { ClinicAdmin, UsuarioAdmin } from '../../api/types';

const ROLE_LABEL: Record<string, string> = {
  super_admin: 'Super-Admin', clinic_admin: 'Admin clínica', branch_admin: 'Admin sucursal',
  medico: 'Médico', empresa: 'Empresa', paciente: 'Paciente', aseguradora: 'Aseguradora',
};
const ASSIGNABLE = ['medico', 'empresa', 'clinic_admin', 'aseguradora'];

export function Usuarios() {
  const navigate = useNavigate();
  const { me } = useAuth();
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [clinicas, setClinicas] = useState<ClinicAdmin[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ nombre: '', correo: '', password: '', role: 'medico', clinic_id: '' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.admin.usuarios().then(setUsuarios);
  useEffect(() => {
    load();
    api.admin.clinicas().then((cs) => {
      setClinicas(cs);
      if (cs[0]) setF((p) => ({ ...p, clinic_id: cs[0].id }));
    });
  }, []);

  const crear = async () => {
    setError(null);
    setSaving(true);
    try {
      await api.admin.crearUsuario({ nombre: f.nombre, correo: f.correo, password: f.password, role: f.role, clinic_id: f.clinic_id });
      setOpen(false);
      setF((p) => ({ ...p, nombre: '', correo: '', password: '' }));
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el usuario');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Usuarios y roles" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {usuarios.map((u) => (
          <div key={u.id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="font-semibold text-sm text-ink">{u.nombre}</div>
            <div className="mt-0.5 text-xs text-sub truncate">{u.email}</div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {u.roles.map((r) => (
                <span key={r.id} className="font-heading font-bold text-[10.5px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark">
                  {ROLE_LABEL[r.role] ?? r.role}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nuevo usuario</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo usuario</div>
          <input value={f.nombre} onChange={(e) => setF((p) => ({ ...p, nombre: e.target.value }))} placeholder="Nombre completo"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={f.correo} onChange={(e) => setF((p) => ({ ...p, correo: e.target.value }))} placeholder="correo@ejemplo.com"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input type="password" value={f.password} onChange={(e) => setF((p) => ({ ...p, password: e.target.value }))} placeholder="Contraseña (mín. 8)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <select value={f.role} onChange={(e) => setF((p) => ({ ...p, role: e.target.value }))}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              {ASSIGNABLE.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
            <select value={f.clinic_id} onChange={(e) => setF((p) => ({ ...p, clinic_id: e.target.value }))}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              {clinicas.map((c) => <option key={c.id} value={c.id}>{c.razon_social}</option>)}
            </select>
          </div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !f.nombre || !f.correo || !f.password} className="w-full">
            {saving ? 'Creando…' : `Crear ${ROLE_LABEL[f.role]}`}
          </Button>
          {me && !me.roles.includes('super_admin') && (
            <div className="text-[11.5px] text-sub text-center">Solo puedes crear usuarios en tu propia clínica.</div>
          )}
        </BottomSheet>
      )}
    </div>
  );
}
