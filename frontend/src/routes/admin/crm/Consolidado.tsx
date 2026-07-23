import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../../components/BackHeader';
import { Button } from '../../../components/Button';
import { Chevron } from '../../../components/ListRow';
import { api } from '../../../api/client';
import type { CrmConsolidado } from '../../../api/types';
import { money, VarBadge } from '../../crm/DetalleClinicaView';

export function Consolidado() {
  const navigate = useNavigate();
  const [data, setData] = useState<CrmConsolidado | null>(null);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    api.crm.consolidado().then(setData);
  }, []);

  const exportar = async () => {
    setExporting(true);
    try {
      const rows = await api.crm.exportar(data?.period);
      const head = ['fecha', 'clinica', 'tipo', 'monto', 'moneda', 'ref'];
      const csv = [
        head.join(','),
        ...rows.map((r) => [r.fecha, r.clinica, r.tipo, r.monto, r.moneda, r.ref ?? ''].map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')),
      ].join('\n');
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `todoscare-asientos-${data?.period ?? ''}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="CRM · Consolidado" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-teal-soft text-teal-dark font-heading font-bold text-[11px] px-3 py-1">
            Alcance: {data?.alcance ?? '…'}
          </span>
          {data && <span className="text-[11px] text-sub">Período {data.period}</span>}
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          <div className="bg-white border border-border rounded-2xl px-4 py-3.5">
            <div className="text-xs text-sub">Ingresos del mes</div>
            <div className="mt-1 font-heading font-extrabold text-[22px] text-ink tabular-nums">{data ? money(data.ingresos_totales) : '—'}</div>
            <div className="mt-1"><VarBadge v={data?.variacion ?? null} /></div>
          </div>
          <div className="bg-white border border-border rounded-2xl px-4 py-3.5">
            <div className="text-xs text-sub">Clínicas · Pacientes</div>
            <div className="mt-1 font-heading font-extrabold text-[22px] text-ink tabular-nums">{data ? `${data.n_clinicas} · ${data.n_pacientes}` : '—'}</div>
          </div>
        </div>

        <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12px] text-teal-dark">
          Cifras derivadas del ledger inmutable y la agenda — el consolidado y cada clínica nunca divergen.
        </div>

        <div className="font-heading font-bold text-[13px] text-ink px-1">Por clínica</div>
        <div className="flex flex-col gap-2.5">
          {data?.clinicas.map((c) => (
            <div
              key={c.clinic_id}
              onClick={() => navigate(`/admin/crm/${c.clinic_id}`)}
              className="flex items-center gap-3 bg-white border border-border rounded-2xl px-4 py-3.5 cursor-pointer"
            >
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{c.razon_social}</div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-sub">
                  <span>{c.pais}</span>·<span>{c.pacientes} paciente(s)</span>·<VarBadge v={c.variacion} />
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="font-heading font-bold text-[14px] text-ink tabular-nums">{money(c.ingresos)}</div>
                <div className="text-[11px] text-sub">margen {c.margen === null ? '—' : `${(c.margen * 100).toFixed(0)}%`}</div>
              </div>
              <Chevron />
            </div>
          ))}
          {data && data.clinicas.length === 0 && <div className="text-center text-sm text-sub py-6">Sin datos en el período.</div>}
        </div>

        <div className="flex flex-col gap-2.5 pt-2">
          <Button onClick={() => navigate('/admin/crm/liquidaciones')} variant="outline" className="w-full">
            Liquidaciones por conciliar
          </Button>
          <Button onClick={exportar} disabled={exporting} variant="ghost" className="w-full">
            {exporting ? 'Exportando…' : 'Exportar asientos a ERP (CSV)'}
          </Button>
        </div>
      </div>
    </div>
  );
}
