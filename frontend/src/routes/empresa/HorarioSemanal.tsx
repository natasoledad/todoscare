import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { BloqueoAgenda, Branch, HorarioTemplate, Profesional, Recinto } from '../../api/types';

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const MOD: Record<string, string> = { presencial: 'Presencial', videoconsulta: 'Video', ambas: 'Presencial + Video' };
const hhmm = (t?: string | null) => (t ? t.slice(0, 5) : '');
const fmtDT = (iso: string) => new Date(iso).toLocaleString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

export function HorarioSemanal() {
  const navigate = useNavigate();
  const [profs, setProfs] = useState<Profesional[]>([]);
  const [sucursales, setSucursales] = useState<Branch[]>([]);
  const [recintos, setRecintos] = useState<Recinto[]>([]);
  const [profId, setProfId] = useState('');
  const [tab, setTab] = useState<'turnos' | 'bloqueos'>('turnos');
  const [horarios, setHorarios] = useState<HorarioTemplate[]>([]);
  const [bloqueos, setBloqueos] = useState<BloqueoAgenda[]>([]);

  const loadHorarios = (pid: string) => api.empresa.horarios(pid).then(setHorarios);
  const loadBloqueos = (pid: string) => api.empresa.bloqueos(pid).then(setBloqueos);
  useEffect(() => {
    Promise.all([api.empresa.profesionales(), api.empresa.sucursales(), api.empresa.recintos()]).then(([p, s, r]) => {
      setProfs(p); setSucursales(s); setRecintos(r);
      if (p[0]) { setProfId(p[0].id); loadHorarios(p[0].id); loadBloqueos(p[0].id); }
    });
  }, []);
  const cambiarProf = (id: string) => { setProfId(id); loadHorarios(id); loadBloqueos(id); };

  // ── alta de bloqueo negativo ──
  const [bloqOpen, setBloqOpen] = useState(false);
  const [bDesde, setBDesde] = useState('');
  const [bHasta, setBHasta] = useState('');
  const [bMotivo, setBMotivo] = useState('');
  const [bBranch, setBBranch] = useState('');
  const [bError, setBError] = useState<string | null>(null);
  const [bSaving, setBSaving] = useState(false);
  const crearBloqueo = async () => {
    setBError(null); setBSaving(true);
    try {
      await api.empresa.crearBloqueo({
        professional_id: profId, branch_id: bBranch || null,
        inicio: new Date(bDesde).toISOString(), fin: new Date(bHasta).toISOString(), motivo: bMotivo || undefined,
      });
      setBDesde(''); setBHasta(''); setBMotivo(''); setBBranch(''); setBloqOpen(false);
      await loadBloqueos(profId);
    } catch (e) {
      setBError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el bloqueo');
    } finally {
      setBSaving(false);
    }
  };
  const eliminarBloqueo = async (id: string) => { await api.empresa.eliminarBloqueo(id); await loadBloqueos(profId); };

  // ── alta / edición de turno ──
  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<string | null>(null);
  const [dia, setDia] = useState(0);
  const [branchId, setBranchId] = useState('');
  const [ini, setIni] = useState('09:00');
  const [fin, setFin] = useState('18:00');
  const [conDescanso, setConDescanso] = useState(false);
  const [descIni, setDescIni] = useState('13:00');
  const [descFin, setDescFin] = useState('14:00');
  const [modalidad, setModalidad] = useState('presencial');
  const [capacidad, setCapacidad] = useState('1');
  const [roomId, setRoomId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const abrirNuevo = () => {
    setEditId(null); setDia(0); setBranchId(sucursales[0]?.id ?? '');
    setIni('09:00'); setFin('18:00'); setConDescanso(false); setDescIni('13:00'); setDescFin('14:00');
    setModalidad('presencial'); setCapacidad('1'); setRoomId(''); setError(null); setOpen(true);
  };
  const abrirEdicion = (h: HorarioTemplate) => {
    setEditId(h.id); setDia(h.dia_semana); setBranchId(h.branch_id);
    setIni(hhmm(h.hora_inicio)); setFin(hhmm(h.hora_fin));
    setConDescanso(!!h.descanso_inicio); setDescIni(hhmm(h.descanso_inicio) || '13:00'); setDescFin(hhmm(h.descanso_fin) || '14:00');
    setModalidad(h.modalidad); setCapacidad(String(h.capacidad)); setRoomId(h.room_id ?? ''); setError(null); setOpen(true);
  };

  const guardar = async () => {
    setError(null); setSaving(true);
    const base = {
      hora_inicio: ini, hora_fin: fin,
      descanso_inicio: conDescanso ? descIni : null, descanso_fin: conDescanso ? descFin : null,
      modalidad, capacidad: Number(capacidad), room_id: roomId || null,
    };
    try {
      if (editId) {
        await api.empresa.editarHorario(editId, base);
      } else {
        await api.empresa.crearHorario({ professional_id: profId, branch_id: branchId, dia_semana: dia, ...base });
      }
      setOpen(false);
      await loadHorarios(profId);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar el turno');
    } finally {
      setSaving(false);
    }
  };
  const eliminar = async (id: string) => { await api.empresa.eliminarHorario(id); await loadHorarios(profId); };

  // ── generar agenda ──
  const [genOpen, setGenOpen] = useState(false);
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [genMsg, setGenMsg] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);
  const generar = async () => {
    setGenerando(true); setGenMsg(null);
    try {
      const r = await api.empresa.generarBloques({ professional_id: profId, desde, hasta });
      setGenMsg(`Se generaron ${r.generados} bloque(s) en ${r.dias} día(s).${r.omitidos ? ` ${r.omitidos} ya existían.` : ''}`);
    } catch (e) {
      setGenMsg(e instanceof ApiError ? String(e.detail) : 'No se pudo generar');
    } finally {
      setGenerando(false);
    }
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Horario semanal" onBack={() => navigate('/empresa')} />

      <div className="px-5 pt-3">
        <label className="font-heading font-semibold text-xs text-sub">Profesional</label>
        <select value={profId} onChange={(e) => cambiarProf(e.target.value)}
          className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
          {profs.map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.specialty_nombre ? ` · ${p.specialty_nombre}` : ''}</option>)}
        </select>
      </div>

      <div className="px-5 pt-3">
        <div className="flex rounded-xl bg-[#EEF2F1] p-1 text-[13px] font-semibold">
          {(['turnos', 'bloqueos'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 rounded-lg py-1.5 capitalize ${tab === t ? 'bg-white text-ink shadow-sm' : 'text-sub'}`}>
              {t === 'turnos' ? 'Turnos' : 'Bloqueos'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-32 flex flex-col gap-2.5">
        {tab === 'turnos' && (<>
        {horarios.length === 0 && <div className="text-center text-sm text-sub py-8">Sin turnos definidos. Agrega el primero — luego «Generar agenda» crea los bloques.</div>}
        {horarios.map((h) => (
          <div key={h.id} className={`rounded-2xl border border-border bg-white px-4 py-3.5 ${h.activo ? '' : 'opacity-60'}`}>
            <div className="flex items-center gap-3">
              <div className="w-14 shrink-0 text-center">
                <div className="text-[11px] font-bold text-teal-dark uppercase">{DIAS[h.dia_semana].slice(0, 3)}</div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink tabular-nums">{hhmm(h.hora_inicio)}–{hhmm(h.hora_fin)}</div>
                <div className="mt-0.5 text-xs text-sub">
                  {h.branch_nombre}{h.room_nombre ? ` · ${h.room_nombre}` : ''} · {MOD[h.modalidad] ?? h.modalidad}
                  {h.capacidad > 1 ? ` · ${h.capacidad} sillones` : ''}
                </div>
                {h.descanso_inicio && <div className="mt-0.5 text-[11px] text-sub">☕ Descanso {hhmm(h.descanso_inicio)}–{hhmm(h.descanso_fin)}</div>}
              </div>
              <div className="flex flex-col items-end gap-1.5">
                <button onClick={() => abrirEdicion(h)} className="text-[13px] font-bold text-teal-dark">Editar</button>
                <button onClick={() => eliminar(h.id)} className="text-[12px] font-bold text-danger">Quitar</button>
              </div>
            </div>
          </div>
        ))}
        </>)}

        {tab === 'bloqueos' && (<>
          {bloqueos.length === 0 && <div className="text-center text-sm text-sub py-8">Sin bloqueos. Crea uno para cerrar la agenda (vacaciones, permiso, feriado).</div>}
          {bloqueos.map((b) => (
            <div key={b.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
              <div className="w-11 h-11 rounded-xl bg-[#FBE9E7] flex items-center justify-center text-lg shrink-0">🚫</div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{b.motivo || 'Bloqueo'}</div>
                <div className="mt-0.5 text-xs text-sub">{fmtDT(b.inicio)} – {fmtDT(b.fin)}{b.branch_nombre ? ` · ${b.branch_nombre}` : ' · Todas las sucursales'}</div>
                {b.creado_por && <div className="mt-0.5 text-[11px] text-sub">Creado por {b.creado_por}</div>}
              </div>
              <div onClick={() => eliminarBloqueo(b.id)} className="cursor-pointer text-[13px] font-bold text-danger">Quitar</div>
            </div>
          ))}
        </>)}
      </div>

      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent flex gap-2">
        {tab === 'turnos' ? (
          <>
            <Button onClick={() => { setGenMsg(null); setGenOpen(true); }} variant="outline" className="flex-1">📅 Generar agenda</Button>
            <Button onClick={abrirNuevo} className="flex-1">+ Nuevo turno</Button>
          </>
        ) : (
          <Button onClick={() => { setBError(null); setBloqOpen(true); }} className="w-full">+ Nuevo bloqueo</Button>
        )}
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">{editId ? 'Editar turno' : 'Nuevo turno'}</div>
          {!editId && (
            <>
              <label className="font-heading font-semibold text-xs text-sub">Día de la semana</label>
              <select value={dia} onChange={(e) => setDia(Number(e.target.value))}
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
                {DIAS.map((d, i) => <option key={d} value={i}>{d}</option>)}
              </select>
              <label className="font-heading font-semibold text-xs text-sub">Sucursal</label>
              <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
                {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
              </select>
            </>
          )}
          <div className="flex gap-2">
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Inicio</label>
              <input type="time" value={ini} onChange={(e) => setIni(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Término</label>
              <input type="time" value={fin} onChange={(e) => setFin(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
          </div>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={conDescanso} onChange={(e) => setConDescanso(e.target.checked)} className="accent-teal" />
            Dar descanso (colación)
          </label>
          {conDescanso && (
            <div className="flex gap-2">
              <input type="time" value={descIni} onChange={(e) => setDescIni(e.target.value)} className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" />
              <input type="time" value={descFin} onChange={(e) => setDescFin(e.target.value)} className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" />
            </div>
          )}
          <div className="flex gap-2">
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Modalidad</label>
              <select value={modalidad} onChange={(e) => setModalidad(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
                <option value="presencial">Presencial</option>
                <option value="videoconsulta">Videoconsulta</option>
                <option value="ambas">Ambas</option>
              </select></div>
            <div className="w-24"><label className="font-heading font-semibold text-xs text-sub">Sillones</label>
              <input value={capacidad} onChange={(e) => setCapacidad(e.target.value)} inputMode="numeric" className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
          </div>
          <label className="font-heading font-semibold text-xs text-sub">Recinto (opcional)</label>
          <select value={roomId} onChange={(e) => setRoomId(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">Sin recinto</option>
            {recintos.map((r) => <option key={r.id} value={r.id}>{r.nombre} ({r.tipo})</option>)}
          </select>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={guardar} disabled={saving} className="w-full">{saving ? 'Guardando…' : editId ? 'Guardar cambios' : 'Agregar turno'}</Button>
        </BottomSheet>
      )}

      {genOpen && (
        <BottomSheet onClose={() => setGenOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Generar agenda</div>
          <div className="text-[12.5px] text-sub">Crea los bloques de disponibilidad a partir del horario semanal, para el rango elegido. Es seguro repetir: no duplica lo ya generado.</div>
          <div className="flex gap-2">
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Desde</label>
              <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Hasta</label>
              <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
          </div>
          {genMsg && <div className="text-xs text-teal-dark">{genMsg}</div>}
          <Button onClick={generar} disabled={!desde || !hasta || generando} className="w-full">{generando ? 'Generando…' : 'Generar bloques'}</Button>
        </BottomSheet>
      )}

      {bloqOpen && (
        <BottomSheet onClose={() => setBloqOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo bloqueo</div>
          <div className="text-[12.5px] text-sub">Cierra la agenda del profesional en este rango (vacaciones, permiso, feriado). No se podrá agendar dentro.</div>
          <div className="flex gap-2">
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Desde</label>
              <input type="datetime-local" value={bDesde} onChange={(e) => setBDesde(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
            <div className="flex-1"><label className="font-heading font-semibold text-xs text-sub">Hasta</label>
              <input type="datetime-local" value={bHasta} onChange={(e) => setBHasta(e.target.value)} className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" /></div>
          </div>
          <input value={bMotivo} onChange={(e) => setBMotivo(e.target.value)} placeholder="Motivo (ej. Vacaciones)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="font-heading font-semibold text-xs text-sub">Sucursal (opcional)</label>
          <select value={bBranch} onChange={(e) => setBBranch(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">Todas las sucursales</option>
            {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </select>
          {bError && <div className="text-xs text-danger">{bError}</div>}
          <Button onClick={crearBloqueo} disabled={!bDesde || !bHasta || bSaving} className="w-full">{bSaving ? 'Guardando…' : 'Crear bloqueo'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}
