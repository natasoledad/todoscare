import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api } from '../../api/client';
import { money } from '../../lib/citas';
import type { LiquidacionDetalle, LiquidacionProf } from '../../api/types';

const thisMonth = () => new Date().toISOString().slice(0, 7);
const fmtDate = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });

export function Liquidaciones() {
  const navigate = useNavigate();
  const [period, setPeriod] = useState(thisMonth());
  const [tab, setTab] = useState<'activas' | 'finalizadas'>('activas');
  const [rows, setRows] = useState<LiquidacionProf[]>([]);
  const [loading, setLoading] = useState(false);

  const load = () => {
    setLoading(true);
    api.empresa.liquidaciones(period, tab).then(setRows).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [period, tab]);

  // ── detalle ──
  const [detProf, setDetProf] = useState<LiquidacionProf | null>(null);
  const [detalle, setDetalle] = useState<LiquidacionDetalle[]>([]);
  const abrirDetalle = async (p: LiquidacionProf) => {
    setDetProf(p); setDetalle([]);
    setDetalle(await api.empresa.liquidacionDetalle(p.professional_id, period, tab));
  };

  // ── finalizar ──
  const [finProf, setFinProf] = useState<LiquidacionProf | null>(null);
  const [finMsg, setFinMsg] = useState<string | null>(null);
  const [finalizando, setFinalizando] = useState(false);
  const confirmarFinalizar = async () => {
    if (!finProf) return;
    setFinalizando(true); setFinMsg(null);
    try {
      const r = await api.empresa.finalizarLiquidacion(finProf.professional_id);
      setFinMsg(`Se finalizaron ${r.finalizadas} prestación(es) por ${money(r.monto)} para ${r.profesional_nombre}.`);
      load();
    } finally {
      setFinalizando(false);
    }
  };

  const totalPagar = rows.reduce((a, r) => a + r.a_pagar, 0);

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Liquidaciones" onBack={() => navigate('/empresa')} />

      <div className="px-5 pt-3 flex items-center gap-2">
        <input type="month" value={period} onChange={(e) => setPeriod(e.target.value)}
          className="rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2 text-sm text-ink outline-none focus:border-teal" />
        <div className="flex-1 text-right text-[13px] text-sub">Total a pagar: <b className="text-ink tabular-nums">{money(totalPagar)}</b></div>
      </div>

      <div className="px-5 pt-3">
        <div className="flex rounded-xl bg-[#EEF2F1] p-1 text-[13px] font-semibold">
          {(['activas', 'finalizadas'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)}
              className={`flex-1 rounded-lg py-1.5 capitalize ${tab === t ? 'bg-white text-ink shadow-sm' : 'text-sub'}`}>
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        {loading && <div className="text-center text-sm text-sub py-8">Cargando…</div>}
        {!loading && rows.length === 0 && <div className="text-center text-sm text-sub py-8">Sin liquidaciones {tab} en este período.</div>}
        {rows.map((r) => (
          <div key={r.professional_id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">🩺</div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{r.nombre}</div>
                <div className="mt-0.5 text-xs text-sub">{r.cantidad} prestación(es) · Realizado {money(r.realizado)}</div>
              </div>
              <div className="text-right">
                <div className="text-[11px] text-sub">A pagar</div>
                <div className="font-heading font-bold text-sm text-ink tabular-nums">{money(r.a_pagar)}</div>
              </div>
            </div>
            <div className="mt-2.5 flex items-center gap-4 pl-14 text-[13px] font-bold">
              <button onClick={() => abrirDetalle(r)} className="text-teal-dark">Ver detalle</button>
              {tab === 'activas' && <button onClick={() => { setFinMsg(null); setFinProf(r); }} className="text-ink">Finalizar</button>}
            </div>
          </div>
        ))}
      </div>

      {detProf && (
        <BottomSheet onClose={() => setDetProf(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Detalle · {detProf.nombre}</div>
          <div className="flex flex-col gap-1.5 max-h-72 overflow-y-auto scrollhide">
            {detalle.length === 0 && <div className="text-center text-[13px] text-sub py-3">Cargando…</div>}
            {detalle.map((d) => (
              <div key={d.split_id} className="flex items-center justify-between rounded-xl border border-border bg-white px-3 py-2">
                <div className="min-w-0">
                  <div className="text-[13px] text-ink truncate">{d.prestacion || 'Prestación'}</div>
                  <div className="text-[11px] text-sub">{fmtDate(d.fecha)}{d.paciente ? ` · ${d.paciente}` : ''}</div>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <div className="text-[13px] font-semibold text-ink tabular-nums">{money(d.monto)}</div>
                  <div className="text-[10.5px] text-sub tabular-nums">base {money(d.base)}</div>
                </div>
              </div>
            ))}
          </div>
        </BottomSheet>
      )}

      {finProf && (
        <BottomSheet onClose={() => setFinProf(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Finalizar liquidación</div>
          <div className="text-[13px] text-sub">Marca como pagadas todas las prestaciones pendientes de <b>{finProf.nombre}</b> ({money(finProf.a_pagar)}) y asienta el egreso. Esta acción no se revierte.</div>
          {finMsg && <div className="text-xs text-teal-dark">{finMsg}</div>}
          <Button onClick={confirmarFinalizar} disabled={finalizando} className="w-full">{finalizando ? 'Finalizando…' : 'Finalizar y pagar'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}
