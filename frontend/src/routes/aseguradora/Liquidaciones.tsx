import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { Convenio, LiquidacionAseg } from '../../api/types';

const currentPeriod = () => new Date().toISOString().slice(0, 7);

export function Liquidaciones() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<LiquidacionAseg[]>([]);
  const [convenios, setConvenios] = useState<Convenio[]>([]);
  const [gen, setGen] = useState(false);
  const [sel, setSel] = useState({ agreement_id: '', periodo: currentPeriod() });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setRows(await api.aseguradora.liquidaciones());
    setConvenios(await api.aseguradora.convenios());
  };
  useEffect(() => { load(); }, []);

  const generar = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.aseguradora.generarLiquidacion(sel.agreement_id || convenios[0]?.agreement_id, sel.periodo);
      setGen(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo generar');
    } finally {
      setBusy(false);
    }
  };

  const pagar = async (id: string) => {
    await api.aseguradora.pagarLiquidacion(id);
    await load();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Liquidaciones" onBack={() => navigate('/aseguradora')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12px] text-teal-dark">
          Generar factura la atención a la clínica (sube su CxC en el ledger); pagar la salda. Todo queda asentado de forma inmutable.
        </div>
        {rows.length === 0 && <div className="text-center text-sm text-sub py-6">Sin liquidaciones aún.</div>}
        {rows.map((s) => (
          <div key={s.settlement_id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{s.clinica}</div>
                <div className="mt-0.5 text-xs text-sub">Período {s.periodo}</div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-heading font-bold text-[15px] text-ink tabular-nums">${s.monto.toLocaleString('es-MX')}</div>
                <StatusTag label={s.estado === 'pagado' ? 'Pagado' : 'Pendiente'} tone={s.estado === 'pagado' ? 'teal' : 'warn'} />
              </div>
            </div>
            {s.estado !== 'pagado' && (
              <div className="mt-3"><Button onClick={() => pagar(s.settlement_id)} className="text-[13px] py-2.5 px-4">Conciliar y pagar</Button></div>
            )}
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => { setGen(true); setError(null); setSel({ agreement_id: convenios[0]?.agreement_id ?? '', periodo: currentPeriod() }); }} className="w-full">+ Generar liquidación</Button>
      </div>

      {gen && (
        <BottomSheet onClose={() => setGen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Generar liquidación</div>
          <div className="text-[12.5px] text-sub">Agrupa las atenciones autorizadas del período y calcula el monto (precio × cobertura).</div>
          <select value={sel.agreement_id} onChange={(e) => setSel((p) => ({ ...p, agreement_id: e.target.value }))}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            {convenios.map((c) => <option key={c.agreement_id} value={c.agreement_id}>{c.clinica}</option>)}
          </select>
          <input value={sel.periodo} onChange={(e) => setSel((p) => ({ ...p, periodo: e.target.value }))} placeholder="Período (YYYY-MM)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={generar} disabled={busy || !sel.agreement_id} className="w-full">{busy ? 'Generando…' : 'Generar'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}
