import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { ClinicAdmin, PerfilAcceso, PerfilAsignado, PermisoCatalogo, PermisoOverride, UsuarioAdmin } from '../../api/types';

const RES_LABEL: Record<string, string> = {
  clinic_agendas: 'Agendas de la clínica', catalogo_precios: 'Catálogo y precios', cajas: 'Cajas',
  tributario: 'Tributario', liquidacion_profesionales: 'Liquidaciones', inventario: 'Inventario',
  laboratorios: 'Laboratorios', promociones: 'Promociones', info_empresa: 'Info empresa',
  funcionarios_b2b: 'Funcionarios B2B', crm_kpis_clinica: 'CRM (KPIs)', crm_campanas: 'CRM campañas',
};
const ACT_LABEL: Record<string, string> = { ver: 'Ver', crear: 'Crear', editar: 'Editar', eliminar: 'Eliminar' };
const resLabel = (r: string) => RES_LABEL[r] ?? r;

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
  const [permUser, setPermUser] = useState<UsuarioAdmin | null>(null);
  const [editUser, setEditUser] = useState<UsuarioAdmin | null>(null);

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
            <div className="mt-2 flex flex-wrap gap-1.5 items-center">
              {u.roles.map((r) => (
                <span key={r.id} className="font-heading font-bold text-[10.5px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark">
                  {ROLE_LABEL[r.role] ?? r.role}
                </span>
              ))}
              {!u.activo && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#F1F1F1] text-sub">inactivo</span>}
              <button onClick={() => setEditUser(u)} className="ml-auto text-[11.5px] font-semibold text-sub">Editar</button>
              {u.roles[0]?.clinic_id && (
                <button onClick={() => setPermUser(u)} className="text-[11.5px] font-semibold text-teal-dark">Accesos ›</button>
              )}
            </div>
          </div>
        ))}
      </div>

      {permUser && <PermisosSheet usuario={permUser} onClose={() => setPermUser(null)} />}
      {editUser && <EditarUsuarioSheet usuario={editUser} onClose={() => setEditUser(null)} onSaved={() => { setEditUser(null); load(); }} />}
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

function PermisosSheet({ usuario, onClose }: { usuario: UsuarioAdmin; onClose: () => void }) {
  const clinicId = usuario.roles[0]?.clinic_id || '';
  const [overrides, setOverrides] = useState<PermisoOverride[]>([]);
  const [cat, setCat] = useState<PermisoCatalogo | null>(null);
  const [resource, setResource] = useState('');
  const [action, setAction] = useState('ver');
  const [allow, setAllow] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Perfiles de acceso reutilizables (48)
  const [perfiles, setPerfiles] = useState<PerfilAcceso[]>([]);
  const [asignado, setAsignado] = useState<PerfilAsignado | null>(null);
  const [perfilSel, setPerfilSel] = useState('');
  const [savingPerfil, setSavingPerfil] = useState(false);

  const load = () => api.admin.permisosUsuario(usuario.id).then(setOverrides).catch(() => setOverrides([]));
  const loadPerfil = () =>
    api.admin.perfilUsuario(usuario.id)
      .then((rows) => setAsignado(rows.find((r) => r.clinic_id === clinicId) ?? null))
      .catch(() => setAsignado(null));
  useEffect(() => {
    load();
    loadPerfil();
    api.admin.perfiles().then((ps) => setPerfiles(ps.filter((p) => p.clinic_id === clinicId && p.activo))).catch(() => setPerfiles([]));
    api.admin.permisosCatalogo().then((c) => { setCat(c); if (c.resources[0]) setResource(c.resources[0]); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usuario.id]);

  const asignarPerfil = async () => {
    if (!clinicId || !perfilSel) return;
    setSavingPerfil(true); setError(null);
    try { await api.admin.asignarPerfil(usuario.id, { clinic_id: clinicId, profile_id: perfilSel }); setPerfilSel(''); await loadPerfil(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo asignar el perfil.'); }
    finally { setSavingPerfil(false); }
  };
  const quitarPerfil = async () => {
    setSavingPerfil(true); setError(null);
    try { await api.admin.quitarPerfil(usuario.id, clinicId); await loadPerfil(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo quitar el perfil.'); }
    finally { setSavingPerfil(false); }
  };

  const guardar = async () => {
    if (!clinicId || !resource) return;
    setSaving(true); setError(null);
    try { await api.admin.setPermisoUsuario(usuario.id, { clinic_id: clinicId, resource, action, allow }); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.'); }
    finally { setSaving(false); }
  };
  const quitar = async (id: string) => { await api.admin.eliminarPermisoUsuario(usuario.id, id); await load(); };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Accesos · {usuario.nombre}</div>

      {/* Perfil de acceso reutilizable (48) */}
      <div className="rounded-xl border border-border bg-[#F6FBF9] px-3 py-2.5 flex flex-col gap-2">
        <div className="text-[12px] font-semibold text-ink">Perfil de acceso</div>
        {asignado ? (
          <div className="flex items-center justify-between">
            <span className="text-[12.5px] text-ink">
              Perfil actual: <span className="font-semibold text-teal-dark">{asignado.profile_nombre}</span>
            </span>
            <button onClick={quitarPerfil} disabled={savingPerfil} className="text-[11px] font-semibold text-danger">Quitar</button>
          </div>
        ) : (
          <div className="text-[11.5px] text-sub">Sin perfil: rige el rol y los ajustes finos de abajo.</div>
        )}
        <div className="flex gap-2">
          <select value={perfilSel} onChange={(e) => setPerfilSel(e.target.value)}
            className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
            <option value="">Elegir perfil…</option>
            {perfiles.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <Button onClick={asignarPerfil} disabled={savingPerfil || !perfilSel} className="shrink-0">
            {asignado ? 'Cambiar' : 'Asignar'}
          </Button>
        </div>
      </div>

      <div className="text-[11.5px] text-sub mt-1">Ajustes finos sobre su rol o perfil: concede o revoca acciones puntuales. Un ajuste fino manda sobre el perfil.</div>

      {overrides.length === 0 && <div className="text-[12px] text-sub">Sin ajustes finos.</div>}
      <div className="flex flex-col gap-1.5">
        {overrides.map((o) => (
          <div key={o.id} className="flex items-center justify-between rounded-xl bg-[#F6FBF9] px-3 py-2">
            <span className="text-[12.5px] text-ink">
              <span className={`font-semibold ${o.allow ? 'text-teal-dark' : 'text-danger'}`}>{o.allow ? 'Concede' : 'Revoca'}</span>{' '}
              {ACT_LABEL[o.action] ?? o.action} · {resLabel(o.resource)}
            </span>
            <button onClick={() => quitar(o.id)} className="text-[11px] font-semibold text-danger">Quitar</button>
          </div>
        ))}
      </div>

      <div className="text-[12px] font-semibold text-ink mt-2">Agregar permiso</div>
      <select value={resource} onChange={(e) => setResource(e.target.value)} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
        {(cat?.resources ?? []).map((r) => <option key={r} value={r}>{resLabel(r)}</option>)}
      </select>
      <div className="flex gap-2">
        <select value={action} onChange={(e) => setAction(e.target.value)} className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
          {(cat?.actions ?? ['ver', 'crear', 'editar', 'eliminar']).map((a) => <option key={a} value={a}>{ACT_LABEL[a] ?? a}</option>)}
        </select>
        <select value={allow ? '1' : '0'} onChange={(e) => setAllow(e.target.value === '1')} className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
          <option value="1">Conceder</option>
          <option value="0">Revocar</option>
        </select>
      </div>
      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={guardar} disabled={saving || !resource} className="w-full">{saving ? 'Guardando…' : 'Aplicar permiso'}</Button>
    </BottomSheet>
  );
}

function EditarUsuarioSheet({ usuario, onClose, onSaved }: { usuario: UsuarioAdmin; onClose: () => void; onSaved: () => void }) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [correo, setCorreo] = useState(usuario.email);
  const [telefono, setTelefono] = useState(usuario.telefono ?? '');
  const [password, setPassword] = useState('');
  const [activo, setActivo] = useState(usuario.activo);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const guardar = async () => {
    setSaving(true); setError(null);
    const body: Record<string, unknown> = {};
    if (nombre !== usuario.nombre) body.nombre = nombre;
    if (correo !== usuario.email) body.correo = correo;
    if (telefono !== (usuario.telefono ?? '')) body.telefono = telefono;
    if (password) body.password = password;
    if (activo !== usuario.activo) body.activo = activo;
    try { await api.admin.editarUsuario(usuario.id, body); onSaved(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.'); setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">Editar · {usuario.nombre}</div>
      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre completo"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      <input value={correo} onChange={(e) => setCorreo(e.target.value)} placeholder="correo@ejemplo.com"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      <input value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Teléfono"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Nueva contraseña (dejar vacío para no cambiar)"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      <label className="flex items-center gap-2.5 py-1">
        <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} className="w-4 h-4 accent-teal" />
        <span className="text-[13px] text-ink">Usuario activo</span>
      </label>
      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={guardar} disabled={saving || !nombre || !correo} className="w-full">{saving ? 'Guardando…' : 'Guardar cambios'}</Button>
    </BottomSheet>
  );
}
