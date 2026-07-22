import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import type { Hospitalizacion } from '../../api/types';

export function Hospitalizaciones() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Hospitalizacion[]>([]);

  useEffect(() => {
    api.salud.hospitalizaciones().then(setRows);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Hospitalizaciones" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-2.5">
        {rows.length === 0 && <div className="text-center text-sm text-sub py-6">Sin hospitalizaciones registradas.</div>}
        {rows.map((h) => (
          <div key={h.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">🏥</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{h.motivo}</div>
              <div className="mt-0.5 text-xs text-sub">
                {h.centro} · {h.ingreso && new Date(h.ingreso).toLocaleDateString('es-MX')}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
