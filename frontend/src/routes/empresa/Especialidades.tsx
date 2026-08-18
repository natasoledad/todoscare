import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { Especialidad, MotivoAtencion, Profesional } from '../../api/types';

type Tab = 'especialidades' | 'perfiles' | 'motivos';

const MODALIDADES: Record<string, string> = {
  presencial: 'Presencial',
  videoconsulta: 'Videoconsulta',
  ambas: 'Presencial + Video',
};

export function Especialidades() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('especialidades');
  const [esps, setEsps] = useState<Especialidad[]>([]);
  const [profs, setProfs] = useState<Profesional[]>([]);
  const [motivos, setMotivos] = useState<MotivoAtencion[]>([]);

  const loadEsps = () => api.empresa.especialidades().then(setEsps);
  const loadProfs = () => api.empresa.profesionales().then(setProfs);
  const loadMotivos = () => api.empresa.motivos().then(setMotivos);
  useEffect(() => { loadEsps(); loadProfs(); loadMotivos(); }, []);

  // ── alta de especialidad ──
  const [espOpen, setEspOpen] = useState(false);
  const [espNombre, setEspNombre] = useState('');
  const [espTipo, setEspTipo] = useState('medica');
  const [espIcono, setEspIcono] = useState('');
  const [espError, setEspError] = useState<string | null>(null);

  const crearEsp = async () => {
    setEspError(null);
    try {
      await api.empresa.crearEspecialidad({ nombre: espNombre, tipo: espTipo, icono: espIcono || undefined });
      setEspNombre(''); setEspIcono(''); setEspTipo('medica'); setEspOpen(false);
      await loadEsps();
    } catch (e) {
      setEspError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la especialidad');
    }
  };
  const toggleEsp = async (s: Especialidad) => {
    await api.empresa.editarEspecialidad(s.id, { activo: !s.activo });
    await loadEsps();
  };

  // ── edición de perfil del profesional ──
  const [perfilProf, setPerfilProf] = useState<Profesional | null>(null);
  const [pSpec, setPSpec] = useState('');
  const [pDur, setPDur] = useState('');
  const [pMod, setPMod] = useState('presencial');
  const [pError, setPError] = useState<string | null>(null);

  const abrirPerfil = (p: Profesional) => {
    setPerfilProf(p);
    setPSpec(p.specialty_id ?? '');
    setPDur(p.duracion_min ? String(p.duracion_min) : '');
    setPMod(p.modalidad ?? 'presencial');
    setPError(null);
  };
  const guardarPerfil = async () => {
    if (!perfilProf) return;
    setPError(null);
    try {
      await api.empresa.editarPerfilProfesional(perfilProf.id, {
        specialty_id: pSpec || null,
        duracion_min: pDur ? Number(pDur) : undefined,
        modalidad: pMod,
      });
      setPerfilProf(null);
      await loadProfs();
    } catch (e) {
      setPError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar el perfil');
    }
  };

  // ── alta de motivo ──
  const [motOpen, setMotOpen] = useState(false);
  const [motNombre, setMotNombre] = useState('');
  const [motSpec, setMotSpec] = useState('');

  const crearMotivo = async () => {
    await api.empresa.crearMotivo({ nombre: motNombre, specialty_id: motSpec || undefined });
    setMotNombre(''); setMotSpec(''); setMotOpen(false);
    await loadMotivos();
  };
  const toggleMotivo = async (m: MotivoAtencion) => {
    await api.empresa.editarMotivo(m.id, { activo: !m.activo });
    await loadMotivos();
  };
  const eliminarMotivo = async (id: string) => {
    await api.empresa.eliminarMotivo(id);
    await loadMotivos();
  };

  const activas = esps.filter((e) => e.activo);
  const tipoLabel = (t?: string | null) => (t === 'dental' ? 'Dental' : t === 'medica' ? 'Médica' : '');

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Especialidades y perfiles" onBack={() => navigate('/empresa')} />

      <div className="px-5 pt-3">
        <div className="flex rounded-xl bg-[#EEF2F1] p-1 text-[13px] font-semibold">
          {(['especialidades', 'perfiles', 'motivos'] as Tab[]).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 rounded-lg py-1.5 capitalize ${tab === t ? 'bg-white text-ink shadow-sm' : 'text-sub'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {/* ───────── ESPECIALIDADES ───────── */}
        {tab === 'especialidades' && (
          <>
            {esps.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no hay especialidades. Crea la primera.</div>}
            {esps.map((s) => (
              <div key={s.id} className={`flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5 ${s.activo ? '' : 'opacity-60'}`}>
                <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">{s.icono || (s.tipo === 'dental' ? '🦷' : '🩺')}</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-ink">{s.nombre}</div>
                  <div className="mt-0.5 text-xs text-sub">{tipoLabel(s.tipo)}</div>
                </div>
                <button onClick={() => toggleEsp(s)}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${s.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                  {s.activo ? 'Habilitada' : 'Deshabilitada'}
                </button>
              </div>
            ))}
          </>
        )}

        {/* ───────── PERFILES DEL PROFESIONAL ───────── */}
        {tab === 'perfiles' && (
          <>
            {profs.length === 0 && <div className="text-center text-sm text-sub py-8">No hay profesionales en la clínica.</div>}
            {profs.map((p) => (
              <div key={p.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
                <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">🩺</div>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-ink">{p.nombre}</div>
                  <div className="mt-0.5 text-xs text-sub">
                    {p.specialty_nombre ? `${p.specialty_nombre}` : 'Sin especialidad'}
                    {p.duracion_min ? ` · ${p.duracion_min} min` : ''}
                    {p.modalidad ? ` · ${MODALIDADES[p.modalidad] ?? p.modalidad}` : ''}
                  </div>
                </div>
                <div onClick={() => abrirPerfil(p)} className="cursor-pointer text-[13px] font-bold text-teal-dark">Editar</div>
              </div>
            ))}
          </>
        )}

        {/* ───────── MOTIVOS DE ATENCIÓN ───────── */}
        {tab === 'motivos' && (
          <>
            {motivos.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no hay motivos de atención.</div>}
            {motivos.map((m) => (
              <div key={m.id} className={`flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5 ${m.activo ? '' : 'opacity-60'}`}>
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-sm text-ink">{m.nombre}</div>
                  <div className="mt-0.5 text-xs text-sub">{m.specialty_nombre ?? 'General'}</div>
                </div>
                <button onClick={() => toggleMotivo(m)}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${m.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                  {m.activo ? 'Activo' : 'Inactivo'}
                </button>
                <div onClick={() => eliminarMotivo(m.id)} className="cursor-pointer text-[13px] font-bold text-danger">Baja</div>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        {tab === 'especialidades' && <Button onClick={() => { setEspError(null); setEspOpen(true); }} className="w-full">+ Nueva especialidad</Button>}
        {tab === 'perfiles' && <div className="text-center text-[12px] text-sub">Toca «Editar» para asignar especialidad, duración y modalidad.</div>}
        {tab === 'motivos' && <Button onClick={() => setMotOpen(true)} className="w-full">+ Nuevo motivo</Button>}
      </div>

      {/* alta especialidad */}
      {espOpen && (
        <BottomSheet onClose={() => setEspOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva especialidad</div>
          <input value={espNombre} onChange={(e) => setEspNombre(e.target.value)} placeholder="Nombre (ej. Ortodoncia)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <select value={espTipo} onChange={(e) => setEspTipo(e.target.value)}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="medica">Médica</option>
              <option value="dental">Dental</option>
            </select>
            <input value={espIcono} onChange={(e) => setEspIcono(e.target.value)} placeholder="Ícono" maxLength={4}
              className="w-20 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal text-center" />
          </div>
          {espError && <div className="text-xs text-danger">{espError}</div>}
          <Button onClick={crearEsp} disabled={!espNombre} className="w-full">Crear especialidad</Button>
        </BottomSheet>
      )}

      {/* edición perfil profesional */}
      {perfilProf && (
        <BottomSheet onClose={() => setPerfilProf(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Perfil de {perfilProf.nombre}</div>
          <label className="font-heading font-semibold text-xs text-sub">Especialidad</label>
          <select value={pSpec} onChange={(e) => setPSpec(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">Sin especialidad</option>
            {activas.map((s) => <option key={s.id} value={s.id}>{s.nombre} ({tipoLabel(s.tipo)})</option>)}
          </select>
          <label className="font-heading font-semibold text-xs text-sub">Duración de cita (min)</label>
          <input value={pDur} onChange={(e) => setPDur(e.target.value)} placeholder="ej. 30" inputMode="numeric"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="font-heading font-semibold text-xs text-sub">Modalidad de atención</label>
          <select value={pMod} onChange={(e) => setPMod(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="presencial">Presencial</option>
            <option value="videoconsulta">Videoconsulta</option>
            <option value="ambas">Presencial + Videoconsulta</option>
          </select>
          {pError && <div className="text-xs text-danger">{pError}</div>}
          <Button onClick={guardarPerfil} className="w-full">Guardar perfil</Button>
        </BottomSheet>
      )}

      {/* alta motivo */}
      {motOpen && (
        <BottomSheet onClose={() => setMotOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo motivo de atención</div>
          <input value={motNombre} onChange={(e) => setMotNombre(e.target.value)} placeholder="Nombre (ej. Control, Urgencia)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="font-heading font-semibold text-xs text-sub">Especialidad (opcional)</label>
          <select value={motSpec} onChange={(e) => setMotSpec(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">General</option>
            {activas.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </select>
          <Button onClick={crearMotivo} disabled={!motNombre} className="w-full">Crear motivo</Button>
        </BottomSheet>
      )}
    </div>
  );
}
