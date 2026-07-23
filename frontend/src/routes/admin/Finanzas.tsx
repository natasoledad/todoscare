import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import type { FinanzasResumen, LedgerEntryAdmin } from '../../api/types';

export function Finanzas() {
  const navigate = useNavigate();
  const [resumen, setResumen] = useState<FinanzasResumen | null>(null);
  const [ledger, setLedger] = useState<LedgerEntryAdmin[]>([]);

  useEffect(() => {
    api.admin.finanzas().then(setResumen);
    api.admin.ledger().then(setLedger);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Finanzas y reportes" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-8 flex flex-col gap-2.5">
        {resumen && (
          <div className="rounded-2xl border border-border bg-white px-1.5">
            {[
              ['Ingresos del mes', resumen.ingresos_mes],
              ['Split a profesionales', resumen.split_profesionales],
              ['Cashback emitido', resumen.cashback_emitido],
            ].map(([label, val], i) => (
              <div key={label as string} className={`flex justify-between px-2.5 py-3 ${i < 2 ? 'border-b border-[#F2F6F5]' : ''}`}>
                <div className="text-[13px] text-sub">{label as string}</div>
                <div className="text-[13px] font-semibold text-ink tabular-nums">${(val as number).toLocaleString('es-MX')}</div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-2 pt-2">
          <div className="font-heading font-bold text-[13px] text-ink">Ledger</div>
          <span className="font-heading font-bold text-[10px] px-2 py-0.5 rounded-full bg-teal-soft text-teal-dark">inmutable · solo lectura</span>
        </div>
        {ledger.length === 0 && <div className="text-sm text-sub">Sin asientos.</div>}
        {ledger.map((e, i) => (
          <div key={i} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[13px] text-ink capitalize">{e.tipo}</div>
              <div className="text-xs text-sub">{new Date(e.fecha).toLocaleDateString('es-MX')}{e.ref ? ` · ${e.ref}` : ''}</div>
            </div>
            <div className="font-heading font-bold text-sm text-ink tabular-nums">${e.monto.toLocaleString('es-MX')} {e.moneda}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
