import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { ClinicAdmin, Conector, TrazaConector } from '../../api/types';

const ICONO: Record<string, string> = {
  Tributario: '🧾', 'Salud / Bonos': '🏥', Pagos: '💳', Mensajería: '💬',
  Marketing: '📣', Presencia: '🌐', Agenda: '📅', Comunicaciones: '☎️',
};
const DIRECCION_LABEL: Record<string, string> = { saliente: 'Envío', entrante: 'Recepción', ambas: 'Envío y recepción' };

export function Conectores() {
  const navigate = useNavigate();
  const [clinicas, setClinicas] = useState<ClinicAdmin[]>([]);
  const [clinicId, setClinicId] = useState('');
  const [conectores, setConectores] = useState<Conector[]>([]);
  const [edit, setEdit] = useState<Conector | null>(null);

  const load = (cid: string) => { if (cid) api.admin.conectores(cid).then(setConectores); };

  useEffect(() => {
    api.admin.clinicas().then((cs) => {
      setClinicas(cs);
      if (cs[0]) { setClinicId(cs[0].id); load(cs[0].id); }
    });
  }, []);

  const onClinic = (cid: string) => { setClinicId(cid); load(cid); };

  // Agrupa por categoría para una lista legible.
  const porCategoria = conectores.reduce<Record<string, Conector[]>>((acc, c) => {
    (acc[c.categoria] ??= []).push(c);
    return acc;
  }, {});

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Conectores (Bloque D)" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-3">
        <div className="text-[12px] text-sub">
          Integraciones con el mundo exterior: SII, I-Med, POS/Klap, Pix, WhatsApp, Meta, TikTok, Google Empresas,
          agenda de terceros, teléfono IP y correo. Activá el conector y guardá sus credenciales por clínica.
          El transporte real se enchufa al tener el contrato; hoy la prueba es simulada y queda en la traza.
        </div>

        <select value={clinicId} onChange={(e) => onClinic(e.target.value)}
          className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
          {clinicas.map((c) => <option key={c.id} value={c.id}>{c.razon_social}</option>)}
        </select>

        {Object.entries(porCategoria).map(([cat, items]) => (
          <div key={cat} className="flex flex-col gap-2">
            <div className="font-heading font-bold text-[12px] text-ink pt-1">{cat}</div>
            {items.map((c) => (
              <div key={c.tipo} onClick={() => setEdit(c)}
                className="flex items-center gap-3 bg-white border border-border rounded-2xl px-4 py-3 cursor-pointer">
                <div className="w-10 h-10 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">{ICONO[c.categoria] ?? '🔌'}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[14px] text-ink truncate">{c.nombre}</div>
                  <div className="mt-0.5 text-[11.5px] text-sub truncate">{c.descripcion}</div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full shrink-0 ${c.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#F1F1F1] text-sub'}`}>
                  {c.activo ? (c.configurado ? 'Activo' : 'Activo · sin datos') : 'Inactivo'}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {edit && (
        <ConectorEditor
          conector={edit}
          clinicId={clinicId}
          onClose={() => setEdit(null)}
          onSaved={() => { setEdit(null); load(clinicId); }}
        />
      )}
    </div>
  );
}

function ConectorEditor({ conector, clinicId, onClose, onSaved }: {
  conector: Conector; clinicId: string; onClose: () => void; onSaved: () => void;
}) {
  const [activo, setActivo] = useState(conector.activo);
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prueba, setPrueba] = useState<string | null>(null);
  const [traza, setTraza] = useState<TrazaConector[]>([]);

  useEffect(() => { api.admin.trazaConector(conector.tipo, clinicId).then(setTraza).catch(() => {}); }, [conector.tipo, clinicId]);

  const yaCargado = (clave: string) => conector.campos_configurados.includes(clave);

  const guardar = async () => {
    setSaving(true); setError(null); setPrueba(null);
    // Solo se envían las claves que el usuario tocó (las vacías borran).
    const credenciales = Object.keys(creds).length ? creds : undefined;
    try {
      await api.admin.configurarConector(conector.tipo, { clinic_id: clinicId, activo, credenciales });
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar el conector.');
      setSaving(false);
    }
  };

  const probar = async () => {
    setSaving(true); setError(null); setPrueba(null);
    try {
      // Guarda antes de probar, para que la prueba use el estado más reciente.
      const credenciales = Object.keys(creds).length ? creds : undefined;
      await api.admin.configurarConector(conector.tipo, { clinic_id: clinicId, activo, credenciales });
      const r = await api.admin.probarConector(conector.tipo, clinicId);
      setPrueba((r.ok ? '✅ ' : '⚠️ ') + r.mensaje);
      api.admin.trazaConector(conector.tipo, clinicId).then(setTraza).catch(() => {});
      setCreds({});
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo probar el conector.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{conector.nombre}</div>
      <div className="text-[12px] text-sub -mt-1">{conector.descripcion}</div>
      <div className="text-[11px] text-teal-dark">Dirección: {DIRECCION_LABEL[conector.direccion] ?? conector.direccion}</div>

      <label className="flex items-center gap-2.5 py-1">
        <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} className="w-4 h-4 accent-teal" />
        <span className="text-[13px] text-ink">Conector activo para esta clínica</span>
      </label>

      <div className="flex flex-col gap-2">
        {conector.campos.map((f) => (
          <div key={f.clave}>
            <label className="text-[11.5px] font-semibold text-sub flex items-center gap-1.5">
              {f.label}{f.secreto && <span className="text-[10px]">🔒</span>}
              {yaCargado(f.clave) && <span className="text-[10px] text-teal-dark">· guardado</span>}
            </label>
            <input
              type={f.secreto ? 'password' : 'text'}
              value={creds[f.clave] ?? ''}
              onChange={(e) => setCreds((p) => ({ ...p, [f.clave]: e.target.value }))}
              placeholder={yaCargado(f.clave) ? '•••••••• (dejar vacío para conservar)' : ''}
              className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal" />
          </div>
        ))}
      </div>

      {prueba && <div className="text-[12px] text-ink bg-[#F6FBF9] rounded-xl px-3 py-2">{prueba}</div>}
      {error && <div className="text-xs text-danger">{error}</div>}

      <div className="flex gap-2">
        <Button onClick={guardar} disabled={saving} className="flex-1">{saving ? 'Guardando…' : 'Guardar'}</Button>
        <Button onClick={probar} disabled={saving} variant="outline" className="flex-1">Probar conexión</Button>
      </div>

      {traza.length > 0 && (
        <div className="pt-1">
          <div className="font-heading font-bold text-[12px] text-ink pb-1">Traza reciente</div>
          <div className="flex flex-col gap-1 max-h-[22vh] overflow-y-auto scrollhide">
            {traza.map((t, i) => (
              <div key={i} className="flex items-center justify-between text-[11.5px] text-sub border-t border-border py-1.5">
                <span>{t.ref ?? t.estado} · {t.direccion}</span>
                <span className="tabular-nums">{new Date(t.fecha).toLocaleString('es-CL')}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </BottomSheet>
  );
}
