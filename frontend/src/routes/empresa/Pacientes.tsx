import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { PacienteLista } from '../../api/types';

const money = (n: number) => `$${n.toLocaleString('es-CL')}`;

export function Pacientes() {
  const navigate = useNavigate();
  const [lista, setLista] = useState<PacienteLista[]>([]);
  const [q, setQ] = useState('');
  const [soloDeuda, setSoloDeuda] = useState(false);
  const [verDeshabilitados, setVerDeshabilitados] = useState(false);

  const load = () => api.empresa.pacientes(verDeshabilitados ? false : true, q || undefined).then(setLista);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [q, verDeshabilitados]);

  const toggle = async (p: PacienteLista) => {
    await api.empresa.cambiarEstadoPaciente(p.id, !p.activo);
    await load();
  };

  const visibles = soloDeuda ? lista.filter((p) => p.deuda > 0) : lista;

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Pacientes" onBack={() => navigate('/empresa')} />
      <div className="px-5 pt-3 flex flex-col gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre…"
          className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal" />
        <div className="flex gap-2 text-[12px]">
          <button onClick={() => setSoloDeuda((v) => !v)} className={`rounded-full px-3 py-1 font-semibold border ${soloDeuda ? 'bg-teal text-white border-teal' : 'bg-white text-sub border-border'}`}>Con deuda</button>
          <button onClick={() => setVerDeshabilitados((v) => !v)} className={`rounded-full px-3 py-1 font-semibold border ${verDeshabilitados ? 'bg-ink text-white border-ink' : 'bg-white text-sub border-border'}`}>{verDeshabilitados ? 'Deshabilitados' : 'Habilitados'}</button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2">
        {visibles.length === 0 && <div className="text-center text-sm text-sub py-8">Sin pacientes.</div>}
        {visibles.map((p) => (
          <div key={p.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{p.nombre}</div>
                <div className="text-[11px] text-sub">RUT {p.rut} · {p.n_tratamientos} tratamiento{p.n_tratamientos === 1 ? '' : 's'}</div>
              </div>
              {p.deuda > 0
                ? <StatusTag label={`Debe ${money(p.deuda)}`} tone="warn" />
                : <StatusTag label="Al día" tone="teal" />}
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className={`text-[11px] font-semibold ${p.activo ? 'text-teal-dark' : 'text-danger'}`}>{p.activo ? 'Habilitado' : 'Deshabilitado'}</span>
              <Button onClick={() => toggle(p)} variant="ghost" className="text-[12px] py-1.5 px-3">{p.activo ? 'Deshabilitar' : 'Habilitar'}</Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
