import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import { money } from '../../lib/citas';
import type { GastosResumen } from '../../api/types';

const thisMonth = () => new Date().toISOString().slice(0, 7);
const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });

export function Gastos() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState(thisMonth());
  const [data, setData] = useState<GastosResumen | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.cajas.gastos(period).then(setData).finally(() => setLoading(false));
  }, [period]);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Gastos" onBack={() => navigate('/empresa')} />
      <div className="px-5 pt-3 flex items-center gap-3">
        <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)}
          className="rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" />
        <div className="flex-1 text-right text-[13px] text-sub">Total del período: <b className="text-danger tabular-nums">{money(data?.total ?? 0)}</b></div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        {loading && <div className="text-center text-sm text-sub py-8">Cargando…</div>}
        {!loading && (!data || data.gastos.length === 0) && <div className="text-center text-sm text-sub py-8">Sin gastos en este período.</div>}
        {data?.gastos.map((g) => (
          <div key={g.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div className="min-w-0">
              <div className="text-[13.5px] text-ink truncate">🔻 {g.glosa || 'Gasto'}</div>
              <div className="text-[11px] text-sub">{fmtDate(g.fecha)} · {g.medio}{g.caja_responsable ? ` · ${g.caja_responsable}` : ''}</div>
            </div>
            <div className="text-[13px] font-semibold text-danger tabular-nums shrink-0 ml-2">−{money(g.monto)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
