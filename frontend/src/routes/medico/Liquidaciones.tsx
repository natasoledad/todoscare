import { useEffect, useState } from 'react';
import { ScreenHeader } from '../../components/ScreenHeader';
import { api } from '../../api/client';
import type { Liquidacion } from '../../api/types';

export function Liquidaciones() {
  const [rows, setRows] = useState<Liquidacion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.medico.liquidaciones().then((r) => {
      setRows(r);
      setLoading(false);
    });
  }, []);

  const total = rows.reduce((s, r) => s + r.monto, 0);

  return (
    <div className="h-full overflow-y-auto scrollhide pb-[90px]">
      <ScreenHeader title="Mis liquidaciones" subtitle="Split de tus atenciones cerradas" />

      <div className="mx-5 mt-2.5 rounded-2xl px-[18px] py-4 text-white bg-gradient-to-br from-teal to-teal-dark">
        <div className="font-heading font-semibold text-[11px] uppercase tracking-wider opacity-85">Total acumulado</div>
        <div className="mt-1 font-heading font-extrabold text-[26px]">${total.toFixed(2)}</div>
      </div>

      <div className="px-5 pt-4 flex flex-col gap-2.5">
        {!loading && rows.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no tienes liquidaciones.</div>}
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">💰</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-[13.5px] text-ink">Atención cerrada</div>
              <div className="text-xs text-sub">
                {new Date(r.fecha).toLocaleDateString('es-MX')}
                {r.base != null && ` · base $${r.base}`}
              </div>
            </div>
            <div className="font-heading font-bold text-sm text-teal">+${r.monto.toFixed(2)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
