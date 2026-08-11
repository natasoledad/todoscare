import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { Bloque, Branch, Profesional, Recinto } from '../../api/types';

export function Agendas() {
  const navigate = useNavigate();
  const [profesionales, setProfesionales] = useState<Profesional[]>([]);
  const [sucursales, setSucursales] = useState<Branch[]>([]);
  const [recintos, setRecintos] = useState<Recinto[]>([]);
  const [bloques, setBloques] = useState<Bloque[]>([]);
  const [open, setOpen] = useState(false);
  const [recOpen, setRecOpen] = useState(false);
  const [profId, setProfId] = useState('');
  const [branchId, setBranchId] = useState('');
  const [roomId, setRoomId] = useState('');
  const [fecha, setFecha] = useState('');
  const [desde, setDesde] = useState('09:00');
  const [hasta, setHasta] = useState('18:00');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // alta de recinto
  const [recNombre, setRecNombre] = useState('');
  const [recNumero, setRecNumero] = useState('');
  const [recTipo, setRecTipo] = useState('medica');
  const [recError, setRecError] = useState<string | null>(null);

  const load = () => api.empresa.agendas().then(setBloques);
  const loadRecintos = () => api.empresa.recintos().then(setRecintos);
  useEffect(() => {
    Promise.all([api.empresa.profesionales(), api.empresa.sucursales(), api.empresa.agendas(), api.empresa.recintos()]).then(([p, s, b, r]) => {
      setProfesionales(p);
      setSucursales(s);
      setBloques(b);
      setRecintos(r);
      if (p[0]) setProfId(p[0].id);
      if (s[0]) setBranchId(s[0].id);
    });
  }, []);

  const crear = async () => {
    setError(null);
    setSaving(true);
    try {
      const inicio = new Date(`${fecha}T${desde}:00`).toISOString();
      const fin = new Date(`${fecha}T${hasta}:00`).toISOString();
      await api.empresa.crearBloque({ professional_id: profId, branch_id: branchId, inicio, fin, room_id: roomId || undefined });
      setOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el bloque');
    } finally {
      setSaving(false);
    }
  };

  const eliminar = async (id: string) => {
    await api.empresa.eliminarBloque(id);
    await load();
  };

  const crearRecinto = async () => {
    setRecError(null);
    try {
      await api.empresa.crearRecinto({ nombre: recNombre, numero: Number(recNumero), tipo: recTipo });
      setRecNombre(''); setRecNumero('');
      await loadRecintos();
    } catch (e) {
      setRecError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el recinto');
    }
  };

  const eliminarRecinto = async (id: string) => {
    await api.empresa.eliminarRecinto(id);
    await loadRecintos();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Configurar agendas" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {bloques.length === 0 && <div className="text-center text-sm text-sub py-8">Sin bloques de disponibilidad. Crea el primero.</div>}
        {bloques.map((b) => (
          <div key={b.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">📅</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{b.professional_nombre}</div>
              <div className="mt-0.5 text-xs text-sub">
                {b.branch_nombre} · {new Date(b.inicio).toLocaleString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                {' – '}{new Date(b.fin).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}
              </div>
              {b.room_nombre && <div className="mt-0.5 text-[11px] font-semibold text-teal-dark">🚪 {b.room_nombre}</div>}
            </div>
            <div onClick={() => eliminar(b.id)} className="cursor-pointer text-[13px] font-bold text-danger">Quitar</div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent flex gap-2">
        <Button onClick={() => { setRecError(null); setRecOpen(true); }} variant="outline" className="flex-1">🚪 Recintos</Button>
        <Button onClick={() => setOpen(true)} className="flex-1">+ Nuevo bloque</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo bloque de disponibilidad</div>
          <label className="font-heading font-semibold text-xs text-sub">Profesional</label>
          <select value={profId} onChange={(e) => setProfId(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal">
            {profesionales.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <label className="font-heading font-semibold text-xs text-sub">Sucursal</label>
          <select value={branchId} onChange={(e) => setBranchId(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal">
            {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </select>
          <label className="font-heading font-semibold text-xs text-sub">Recinto (sala/box)</label>
          <select value={roomId} onChange={(e) => setRoomId(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">Sin recinto asignado</option>
            {recintos.map((r) => <option key={r.id} value={r.id}>{r.nombre} ({r.tipo})</option>)}
          </select>
          <input type="date" value={fecha} onChange={(e) => setFecha(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <input type="time" value={desde} onChange={(e) => setDesde(e.target.value)}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input type="time" value={hasta} onChange={(e) => setHasta(e.target.value)}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={!fecha || !profId || !branchId || saving} className="w-full">
            {saving ? 'Publicando…' : 'Publicar disponibilidad'}
          </Button>
        </BottomSheet>
      )}

      {recOpen && (
        <BottomSheet onClose={() => setRecOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Recintos (salas / boxes)</div>
          <div className="text-[12px] text-sub">Un profesional por recinto a la vez: la agenda no deja agendar dos profesionales en la misma sala/box en el mismo horario.</div>
          <div className="flex flex-col gap-1.5 max-h-52 overflow-y-auto scrollhide">
            {recintos.length === 0 && <div className="text-center text-[13px] text-sub py-3">Aún no hay recintos.</div>}
            {recintos.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-xl border border-border bg-white px-3 py-2">
                <div className="text-[13px] text-ink">{r.nombre} <span className="text-[11px] text-sub">· {r.tipo}</span></div>
                <div onClick={() => eliminarRecinto(r.id)} className="cursor-pointer text-[12px] font-bold text-danger">Quitar</div>
              </div>
            ))}
          </div>
          <div className="pt-1 font-heading font-semibold text-xs text-sub">Agregar recinto</div>
          <input value={recNombre} onChange={(e) => setRecNombre(e.target.value)} placeholder="Nombre (ej. Sala Médica 1)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <input value={recNumero} onChange={(e) => setRecNumero(e.target.value)} placeholder="N°" inputMode="numeric"
              className="w-20 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <select value={recTipo} onChange={(e) => setRecTipo(e.target.value)}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="medica">Sala médica</option>
              <option value="dental">Box dental</option>
            </select>
          </div>
          {recError && <div className="text-xs text-danger">{recError}</div>}
          <Button onClick={crearRecinto} disabled={!recNombre || !recNumero} className="w-full">Agregar recinto</Button>
        </BottomSheet>
      )}
    </div>
  );
}
