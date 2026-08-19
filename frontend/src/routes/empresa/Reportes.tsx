import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api, ApiError } from '../../api/client';
import type { AgendaKpis, ReporteBib } from '../../api/types';

const pct = (n: number) => `${Math.round(n * 100)}%`;

/** Reportería / BI (68): KPIs de agenda + biblioteca de reportes con export CSV. */
export function Reportes() {
  const navigate = useNavigate();
  const [kpis, setKpis] = useState<AgendaKpis | null>(null);
  const [bib, setBib] = useState<ReporteBib[]>([]);
  const [bajando, setBajando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reportes.agendaKpis(30).then(setKpis).catch(() => setKpis(null));
    api.reportes.biblioteca().then(setBib).catch(() => setBib([]));
  }, []);

  const descargar = async (r: ReporteBib) => {
    setBajando(r.id); setError(null);
    try {
      const blob = await api.reportes.exportar(r.id, 30);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `${r.id}_30d.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo descargar.'); }
    finally { setBajando(null); }
  };

  const categorias = [...new Set(bib.map((r) => r.categoria))];

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Reportes" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-8 flex flex-col gap-5">
        {/* KPIs de agenda */}
        {kpis && (
          <div>
            <div className="font-heading font-bold text-[13px] text-ink mb-2">Agenda · últimos {kpis.dias} días</div>
            <div className="grid grid-cols-2 gap-2">
              <Kpi label="Ocupación" value={pct(kpis.ocupacion_pct)} />
              <Kpi label="No-show" value={pct(kpis.no_show_pct)} tone={kpis.no_show_pct > 0.15 ? 'warn' : 'ok'} />
              <Kpi label="Espera promedio" value={`${kpis.tiempo_espera_prom_min} min`} />
              <Kpi label="Citas" value={String(kpis.total_citas)} />
            </div>
            <div className="text-[11px] text-sub mt-1.5">{kpis.completadas} completadas · {kpis.no_shows} inasistencias · {kpis.atendidas_con_espera} con espera medida</div>
          </div>
        )}

        {/* Biblioteca de reportes */}
        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Biblioteca de reportes</div>
          {error && <div className="text-xs text-danger mb-2">{error}</div>}
          <div className="flex flex-col gap-3">
            {categorias.map((cat) => (
              <div key={cat}>
                <div className="text-[11px] font-semibold uppercase tracking-wide text-sub mb-1.5">{cat}</div>
                <div className="flex flex-col gap-2">
                  {bib.filter((r) => r.categoria === cat).map((r) => (
                    <div key={r.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
                      <div className="min-w-0 pr-2">
                        <div className="font-semibold text-[13.5px] text-ink">{r.nombre}</div>
                        <div className="text-[11px] text-sub">{r.descripcion}</div>
                      </div>
                      {r.exportable && (
                        <button onClick={() => descargar(r)} disabled={bajando === r.id}
                          className="shrink-0 rounded-lg bg-teal-soft px-3 py-1.5 text-[12px] font-semibold text-teal-dark disabled:opacity-60">
                          {bajando === r.id ? '…' : 'CSV'}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, tone }: { label: string; value: string; tone?: 'ok' | 'warn' }) {
  return (
    <div className="rounded-2xl border border-border bg-white px-4 py-3">
      <div className={`font-heading font-extrabold text-[22px] tabular-nums ${tone === 'warn' ? 'text-danger' : 'text-teal-dark'}`}>{value}</div>
      <div className="text-[11.5px] text-sub mt-0.5">{label}</div>
    </div>
  );
}
