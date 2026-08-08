import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import { money } from '../../lib/citas';
import type { Desempeno as DesempenoData } from '../../api/types';

function Tile({ label, value, tone }: { label: string; value: string; tone?: 'good' }) {
  return (
    <div className="rounded-2xl border border-border bg-white px-3.5 py-3">
      <div className="text-[11px] text-sub">{label}</div>
      <div className={`mt-0.5 font-heading font-extrabold text-[19px] tabular-nums ${tone === 'good' ? 'text-teal-dark' : 'text-ink'}`}>{value}</div>
    </div>
  );
}

export function Desempeno() {
  const navigate = useNavigate();
  const [d, setD] = useState<DesempenoData | null>(null);

  useEffect(() => { api.empresa.desempeno().then(setD); }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Panel de desempeño" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-4">
        {!d && <div className="text-center text-sub text-sm py-8">Cargando…</div>}
        {d && (
          <>
            <div className="text-[12px] text-sub -mb-1">Período {d.periodo}</div>
            <div className="grid grid-cols-2 gap-2">
              <Tile label="Ventas (facturado)" value={money(d.ventas)} />
              <Tile label="Recaudado (caja)" value={money(d.recaudado)} tone="good" />
              <Tile label="Atenciones" value={String(d.atenciones)} />
              <Tile label="Ticket medio" value={money(d.ticket_medio)} />
            </div>

            {/* Por profesional */}
            <div>
              <div className="font-heading font-bold text-[13px] text-ink mb-2">Por profesional</div>
              {d.por_profesional.length === 0 && <div className="text-sm text-sub">Sin datos del período.</div>}
              <div className="rounded-2xl border border-border bg-white overflow-hidden">
                {d.por_profesional.map((p, i) => (
                  <div key={p.nombre} className={`px-4 py-3 ${i > 0 ? 'border-t border-[#F2F6F5]' : ''}`}>
                    <div className="flex items-center justify-between">
                      <div className="font-semibold text-[13.5px] text-ink truncate">{p.nombre}</div>
                      <div className="text-[13px] font-bold text-ink tabular-nums">{money(p.ventas)}</div>
                    </div>
                    <div className="mt-0.5 flex items-center justify-between text-[11px] text-sub">
                      <span>{p.atenciones} atención{p.atenciones === 1 ? '' : 'es'}</span>
                      <span>A pagar <strong className="text-teal-dark">{money(p.a_pagar)}</strong>{p.pct != null ? ` · ${p.pct}%` : ''}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Por grupo de servicio */}
            <div>
              <div className="font-heading font-bold text-[13px] text-ink mb-2">Por grupo de servicio</div>
              {d.por_grupo.length === 0 && <div className="text-sm text-sub">Sin datos del período.</div>}
              <div className="rounded-2xl border border-border bg-white overflow-hidden">
                {d.por_grupo.map((g, i) => (
                  <div key={g.grupo} className={`flex items-center justify-between px-4 py-3 ${i > 0 ? 'border-t border-[#F2F6F5]' : ''}`}>
                    <div className="min-w-0">
                      <div className="font-semibold text-[13.5px] text-ink truncate">{g.grupo}</div>
                      <div className="text-[11px] text-sub">{g.cantidad} · ticket {money(g.ticket_medio)}</div>
                    </div>
                    <div className="text-[13px] font-bold text-ink tabular-nums">{money(g.monto)}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="text-[11px] text-sub text-center">Todo se calcula del ledger y la agenda; nada se almacena.</div>
          </>
        )}
      </div>
    </div>
  );
}
