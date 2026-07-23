import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Chevron } from '../../components/ListRow';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { EmpresaKpis } from '../../api/types';

const MODULES = [
  { id: 'crm', icon: '📈', t: 'Indicadores (CRM)', d: 'Ingresos, margen, ocupación de tu clínica' },
  { id: 'agendas', icon: '📅', t: 'Configurar agendas', d: 'Horarios por profesional y sucursal' },
  { id: 'servicios', icon: '🏷️', t: 'Productos y servicios', d: 'Catálogo y precios' },
  { id: 'promociones', icon: '📣', t: 'Promociones', d: 'Ofertas para pacientes' },
  { id: 'info', icon: 'ℹ️', t: 'Información de la empresa', d: 'Datos, responsable, ubicaciones' },
  { id: 'funcionarios', icon: '👥', t: 'Funcionarios (B2B)', d: 'Nómina cubierta y planes' },
];

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-border rounded-2xl px-4 py-3.5">
      <div className="text-xs text-sub">{label}</div>
      <div className="mt-1 font-heading font-extrabold text-[22px] text-ink tabular-nums">{value}</div>
    </div>
  );
}

export function Inicio() {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [kpis, setKpis] = useState<EmpresaKpis | null>(null);

  useEffect(() => {
    api.empresa.inicio().then(setKpis);
  }, []);

  return (
    <div className="h-full overflow-y-auto scrollhide pb-8">
      <div className="flex items-start justify-between px-[22px] pt-5 pb-1">
        <div>
          <div className="text-[13px] text-sub">Portal Empresa</div>
          <div className="font-heading font-extrabold text-xl text-ink">{kpis?.clinic_nombre ?? '…'}</div>
        </div>
        <div className="w-[42px] h-[42px] rounded-full bg-teal-soft flex items-center justify-center text-lg">🏥</div>
      </div>

      <div className="mx-5 mt-3.5 grid grid-cols-2 gap-2.5">
        <Kpi label="Citas hoy" value={kpis ? String(kpis.citas_hoy) : '—'} />
        <Kpi label="Ingresos del mes" value={kpis ? `$${kpis.ingresos_mes.toLocaleString('es-MX')}` : '—'} />
        <Kpi label="Servicios activos" value={kpis ? String(kpis.servicios_activos) : '—'} />
        <Kpi label="Promos activas" value={kpis ? String(kpis.promos_activas) : '—'} />
      </div>

      {kpis && kpis.mas_vendidos.length > 0 && (
        <>
          <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Servicios más vendidos</div>
          <div className="mx-5 mt-2.5 rounded-2xl border border-border bg-white px-1.5">
            {kpis.mas_vendidos.map((s, i) => (
              <div key={s.nombre} className={`flex justify-between px-2.5 py-3 ${i < kpis.mas_vendidos.length - 1 ? 'border-b border-[#F2F6F5]' : ''}`}>
                <div className="text-[13px] text-ink">{s.nombre}</div>
                <div className="text-[13px] font-semibold text-sub tabular-nums">{s.cantidad}</div>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Gestión</div>
      <div className="px-5 pt-2.5 flex flex-col gap-2.5">
        {MODULES.map((m) => (
          <div
            key={m.id}
            onClick={() => navigate(`/empresa/${m.id}`)}
            className="flex items-center gap-3.5 bg-white border border-border rounded-2xl px-4 py-3.5 cursor-pointer"
          >
            <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-xl shrink-0">{m.icon}</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-[14.5px] text-ink">{m.t}</div>
              <div className="mt-0.5 text-xs text-sub">{m.d}</div>
            </div>
            <Chevron />
          </div>
        ))}
      </div>

      <div className="px-5 pt-6">
        <Button onClick={() => { logout(); navigate('/'); }} variant="outline" className="w-full">
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}
