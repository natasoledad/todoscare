import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api } from '../../api/client';
import type { EntidadFinanciera } from '../../api/types';

export function EntidadesFinancieras() {
  const navigate = useNavigate();
  const [entidades, setEntidades] = useState<EntidadFinanciera[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [tipo, setTipo] = useState('banco');
  const [saving, setSaving] = useState(false);

  const load = () => api.empresa.entidadesFinancieras().then(setEntidades);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    await api.empresa.crearEntidad({ nombre, tipo });
    setNombre(''); setTipo('banco'); setOpen(false);
    await load();
    setSaving(false);
  };
  const toggle = async (e: EntidadFinanciera) => { await api.empresa.editarEntidad(e.id, { activo: !e.activo }); await load(); };
  const eliminar = async (id: string) => { await api.empresa.eliminarEntidad(id); await load(); };

  const label = (t: string) => (t === 'isapre' ? 'Isapre / Fonasa' : 'Banco');

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Bancos e Isapres" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {entidades.length === 0 && <div className="text-center text-sm text-sub py-8">Sin entidades. Agrega bancos e Isapres/Fonasa.</div>}
        {entidades.map((e) => (
          <div key={e.id} className={`flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5 ${e.activo ? '' : 'opacity-60'}`}>
            <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">{e.tipo === 'isapre' ? '🏥' : '🏦'}</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{e.nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{label(e.tipo)}</div>
            </div>
            <button onClick={() => toggle(e)}
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${e.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
              {e.activo ? 'Habilitada' : 'Deshabilitada'}
            </button>
            <div onClick={() => eliminar(e.id)} className="cursor-pointer text-[13px] font-bold text-danger">Baja</div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nueva entidad</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva entidad</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Banco Estado, Fonasa)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="font-heading font-semibold text-xs text-sub">Tipo</label>
          <select value={tipo} onChange={(e) => setTipo(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="banco">Banco</option>
            <option value="isapre">Isapre / Fonasa</option>
          </select>
          <Button onClick={crear} disabled={!nombre || saving} className="w-full">{saving ? 'Guardando…' : 'Crear entidad'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}
