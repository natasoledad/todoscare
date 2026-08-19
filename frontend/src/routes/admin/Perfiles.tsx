import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { ClinicAdmin, PerfilAcceso, PermisoCatalogo, PermisoItem } from '../../api/types';

const RES_LABEL: Record<string, string> = {
  clinic_agendas: 'Agendas de la clínica', catalogo_precios: 'Catálogo y precios', promociones: 'Promociones',
  info_empresa: 'Info de la empresa', funcionarios_b2b: 'Funcionarios B2B', cajas: 'Cajas',
  tributario: 'Tributario', liquidacion_profesionales: 'Liquidaciones', inventario: 'Inventario',
  laboratorios: 'Laboratorios', crm_kpis_clinica: 'CRM (KPIs)', crm_campanas: 'CRM campañas',
  own_agenda: 'Mi agenda', prontuario_atendidos: 'Ficha de atendidos', prescripciones: 'Prescripciones',
  ordenes_examen: 'Órdenes de examen', liquidacion_propia: 'Mi liquidación',
};
const ACT_LABEL: Record<string, string> = { ver: 'Ver', crear: 'Crear', editar: 'Editar', eliminar: 'Eliminar' };
const ROLE_LABEL: Record<string, string> = { empresa: 'Empresa', medico: 'Médico/Profesional', clinic_admin: 'Administración' };
const BASE_ROLES = ['empresa', 'medico', 'clinic_admin'];
// Recursos que se ofrecen en el grid según el panel (rol base) del perfil.
const RES_BY_ROLE: Record<string, string[]> = {
  empresa: ['clinic_agendas', 'catalogo_precios', 'promociones', 'info_empresa', 'funcionarios_b2b', 'cajas', 'tributario', 'liquidacion_profesionales', 'inventario', 'laboratorios', 'crm_kpis_clinica', 'crm_campanas'],
  medico: ['own_agenda', 'prontuario_atendidos', 'prescripciones', 'ordenes_examen', 'liquidacion_propia'],
  clinic_admin: ['clinicas_sucursales', 'usuarios_roles', 'ledger_financiero', 'ficha_clinica_metadatos', 'crm_kpis_clinica'],
};

const keyOf = (r: string, a: string) => `${r}::${a}`;

export function Perfiles() {
  const navigate = useNavigate();
  const [perfiles, setPerfiles] = useState<PerfilAcceso[]>([]);
  const [clinicas, setClinicas] = useState<ClinicAdmin[]>([]);
  const [cat, setCat] = useState<PermisoCatalogo | null>(null);
  const [edit, setEdit] = useState<PerfilAcceso | 'nuevo' | null>(null);

  const load = () => api.admin.perfiles().then(setPerfiles);
  useEffect(() => {
    load();
    api.admin.clinicas().then(setClinicas);
    api.admin.permisosCatalogo().then(setCat);
  }, []);

  const nombreClinica = (id: string) => clinicas.find((c) => c.id === id)?.razon_social ?? '';

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Perfiles de acceso" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        <div className="text-[12px] text-sub">
          Un perfil junta las casillas de acceso que definís una vez. Luego lo asignás a un usuario en un clic desde «Usuarios y roles».
        </div>
        {perfiles.map((p) => (
          <div key={p.id} className="rounded-2xl border border-border bg-white px-4 py-3.5" onClick={() => setEdit(p)}>
            <div className="flex items-center gap-2">
              <div className="font-semibold text-sm text-ink">{p.nombre}</div>
              {!p.activo && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#F1F1F1] text-sub">inactivo</span>}
            </div>
            <div className="mt-0.5 text-xs text-sub">
              {ROLE_LABEL[p.base_role] ?? p.base_role} · {nombreClinica(p.clinic_id)}
            </div>
            <div className="mt-1.5 text-[11.5px] text-teal-dark">
              {p.sin_restriccion ? 'Acceso total (sin restricción)' : `${p.permisos.length} accesos · ${p.usuarios} usuario(s)`}
            </div>
          </div>
        ))}
      </div>

      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setEdit('nuevo')} className="w-full">+ Nuevo perfil</Button>
      </div>

      {edit && cat && (
        <PerfilEditor
          perfil={edit === 'nuevo' ? null : edit}
          clinicas={clinicas}
          cat={cat}
          onClose={() => setEdit(null)}
          onSaved={() => { setEdit(null); load(); }}
        />
      )}
    </div>
  );
}

function PerfilEditor({
  perfil, clinicas, cat, onClose, onSaved,
}: {
  perfil: PerfilAcceso | null;
  clinicas: ClinicAdmin[];
  cat: PermisoCatalogo;
  onClose: () => void;
  onSaved: () => void;
}) {
  const esNuevo = perfil === null;
  const [nombre, setNombre] = useState(perfil?.nombre ?? '');
  const [baseRole, setBaseRole] = useState(perfil?.base_role ?? 'empresa');
  const [clinicId, setClinicId] = useState(perfil?.clinic_id ?? clinicas[0]?.id ?? '');
  const [sinRestriccion, setSinRestriccion] = useState(perfil?.sin_restriccion ?? false);
  const [sel, setSel] = useState<Set<string>>(new Set((perfil?.permisos ?? []).map((p) => keyOf(p.resource, p.action))));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const actions = cat.actions.length ? cat.actions : ['ver', 'crear', 'editar', 'eliminar'];
  const recursos = useMemo(() => {
    const base = RES_BY_ROLE[baseRole] ?? cat.resources;
    return base.filter((r) => cat.resources.includes(r) || RES_LABEL[r]);
  }, [baseRole, cat.resources]);

  const toggle = (r: string, a: string) => {
    setSel((prev) => {
      const n = new Set(prev);
      const k = keyOf(r, a);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  };

  const guardar = async () => {
    setSaving(true); setError(null);
    const permisos: PermisoItem[] = [...sel].map((k) => {
      const [resource, action] = k.split('::');
      return { resource, action };
    });
    try {
      if (esNuevo) {
        await api.admin.crearPerfil({ clinic_id: clinicId, nombre, base_role: baseRole, permisos, sin_restriccion: sinRestriccion });
      } else {
        await api.admin.editarPerfil(perfil!.id, { nombre, permisos, sin_restriccion: sinRestriccion });
      }
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar el perfil.');
    } finally {
      setSaving(false);
    }
  };

  const eliminar = async () => {
    if (!perfil) return;
    setSaving(true); setError(null);
    try { await api.admin.eliminarPerfil(perfil.id); onSaved(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo eliminar.'); setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{esNuevo ? 'Nuevo perfil' : `Editar · ${perfil?.nombre}`}</div>

      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del perfil (p. ej. Recepción)"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />

      <div className="flex gap-2">
        <select value={baseRole} onChange={(e) => setBaseRole(e.target.value)} disabled={!esNuevo}
          className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal disabled:opacity-60">
          {BASE_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
        </select>
        {esNuevo && (
          <select value={clinicId} onChange={(e) => setClinicId(e.target.value)}
            className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            {clinicas.map((c) => <option key={c.id} value={c.id}>{c.razon_social}</option>)}
          </select>
        )}
      </div>

      <label className="flex items-center gap-2.5 py-1">
        <input type="checkbox" checked={sinRestriccion} onChange={(e) => setSinRestriccion(e.target.checked)} className="w-4 h-4 accent-teal" />
        <span className="text-[13px] text-ink">Acceso total al panel (sin restricción)</span>
      </label>

      {!sinRestriccion && (
        <div className="rounded-xl border border-border overflow-hidden">
          <div className="flex items-center bg-[#F6FBF9] px-3 py-2">
            <div className="flex-1 text-[11px] font-semibold text-sub">Acceso</div>
            {actions.map((a) => <div key={a} className="w-12 text-center text-[10.5px] font-semibold text-sub">{ACT_LABEL[a] ?? a}</div>)}
          </div>
          <div className="max-h-[40vh] overflow-y-auto scrollhide">
            {recursos.map((r) => (
              <div key={r} className="flex items-center px-3 py-2 border-t border-border">
                <div className="flex-1 text-[12.5px] text-ink pr-2">{RES_LABEL[r] ?? r}</div>
                {actions.map((a) => (
                  <div key={a} className="w-12 flex justify-center">
                    <input type="checkbox" checked={sel.has(keyOf(r, a))} onChange={() => toggle(r, a)} className="w-4 h-4 accent-teal" />
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}

      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={guardar} disabled={saving || !nombre || (esNuevo && !clinicId)} className="w-full">
        {saving ? 'Guardando…' : esNuevo ? 'Crear perfil' : 'Guardar cambios'}
      </Button>
      {!esNuevo && (
        <button onClick={eliminar} disabled={saving} className="w-full text-[12.5px] font-semibold text-danger py-1.5">Eliminar perfil</button>
      )}
    </BottomSheet>
  );
}
