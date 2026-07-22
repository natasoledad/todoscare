import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import type { Odontograma } from '../../api/types';

export function Dental() {
  const navigate = useNavigate();
  const [odontograma, setOdontograma] = useState<Odontograma | null>(null);

  useEffect(() => {
    api.salud.dental().then(setOdontograma);
  }, []);

  const piezas = odontograma?.piezas || {};
  const keys = Object.keys(piezas).length > 0 ? Object.keys(piezas) : Array.from({ length: 16 }, (_, i) => String(i));
  const pendientes = keys.filter((k) => piezas[k]?.estado === 'pendiente');

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Ficha dental" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        <div className="font-heading font-bold text-[13px] text-ink">Odontograma</div>
        <div className="bg-white border border-border rounded-2xl p-4 grid grid-cols-8 gap-1.5">
          {keys.map((k) => (
            <div key={k} className={`aspect-square rounded-md border border-border-strong ${piezas[k]?.estado === 'pendiente' ? 'bg-[#F6D9CF]' : 'bg-[#F2F6F5]'}`} />
          ))}
        </div>
        {pendientes.length > 0 && (
          <div className="text-[11.5px] text-sub">Pieza{pendientes.length > 1 ? 's' : ''} {pendientes.join(', ')} con tratamiento pendiente</div>
        )}
      </div>
    </div>
  );
}
