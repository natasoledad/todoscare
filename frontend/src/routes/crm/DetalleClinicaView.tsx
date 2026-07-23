import type { CrmDetalleClinica } from '../../api/types';

export const money = (n: number) => `$${Math.round(n).toLocaleString('es-MX')}`;

export function pct(n: number | null): string {
  if (n === null) return '—';
  const s = (n * 100).toFixed(1).replace(/\.0$/, '');
  return `${n >= 0 ? '' : ''}${s}%`;
}

/** ▲/▼ de variación mes-vs-mes con color (verde sube, rojo baja). */
export function VarBadge({ v }: { v: number | null }) {
  if (v === null) return <span className="text-[11px] text-sub">sin base</span>;
  const up = v >= 0;
  return (
    <span className={`text-[11px] font-bold ${up ? 'text-teal-dark' : 'text-danger'}`}>
      {up ? '▲' : '▼'} {pct(Math.abs(v))}
    </span>
  );
}

/** Detalle de KPIs de una clínica — compartido por el Admin (drill-down) y la
 *  Empresa (su propia clínica). Todo se calcula en el backend desde el ledger
 *  + agenda; aquí solo se presenta. */
export function DetalleClinicaView({ d }: { d: CrmDetalleClinica }) {
  const kpis: [string, string, JSX.Element | null][] = [
    ['Ingresos del mes', money(d.ingresos), <VarBadge key="v" v={d.variacion} />],
    ['Margen', pct(d.margen), null],
    ['Ticket promedio', money(d.ticket_promedio), null],
    ['Atenciones', String(d.n_atenciones), null],
    ['Ocupación de agenda', pct(d.ocupacion), null],
    ['Cuentas por cobrar', money(d.cuentas_por_cobrar), null],
    ['Por liquidar a prestadores', money(d.por_liquidar), null],
  ];
  return (
    <div className="flex flex-col gap-3">
      <div className="rounded-2xl border border-border bg-white px-1.5">
        {kpis.map(([label, val, extra], i) => (
          <div key={label} className={`flex items-center justify-between px-3 py-3 ${i < kpis.length - 1 ? 'border-b border-[#F2F6F5]' : ''}`}>
            <div className="text-[13px] text-sub">{label}</div>
            <div className="flex items-center gap-2">
              {extra}
              <div className="text-[13.5px] font-semibold text-ink tabular-nums">{val}</div>
            </div>
          </div>
        ))}
      </div>

      <div>
        <div className="font-heading font-bold text-[13px] text-ink px-1 pb-2">Ingresos por servicio</div>
        {d.ingresos_por_servicio.length === 0 ? (
          <div className="text-[13px] text-sub px-1">Sin ingresos de atención en el período.</div>
        ) : (
          <div className="rounded-2xl border border-border bg-white px-1.5">
            {d.ingresos_por_servicio.map((s, i) => (
              <div key={s.servicio} className={`flex justify-between px-3 py-3 ${i < d.ingresos_por_servicio.length - 1 ? 'border-b border-[#F2F6F5]' : ''}`}>
                <div className="text-[13px] text-ink">{s.servicio}</div>
                <div className="text-[13px] font-semibold text-sub tabular-nums">{money(s.monto)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
