import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/Button';
import { Chevron } from '../../components/ListRow';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { AdminKpis } from '../../api/types';

const MODULES = [
  { id: 'clinicas', icon: '🏥', t: 'Clínicas y sucursales', d: 'Alta de tenants, sucursales, baja' },
  { id: 'usuarios', icon: '👥', t: 'Usuarios y roles', d: 'Pacientes, médicos, empresas' },
  { id: 'config', icon: '⚙️', t: 'Configuración global', d: 'Planes y T&C por país' },
  { id: 'finanzas', icon: '📊', t: 'Finanzas y reportes', d: 'Ledger inmutable y split' },
  { id: 'auditoria', icon: '🔒', t: 'Auditoría', d: 'Accesos y cambios (metadatos)' },
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
  const { me, logout } = useAuth();
  const [kpis, setKpis] = useState<AdminKpis | null>(null);

  useEffect(() => {
    api.admin.inicio().then(setKpis);
  }, []);

  return (
    <div className="h-full overflow-y-auto scrollhide pb-8">
      <div className="flex items-start justify-between px-[22px] pt-5 pb-1">
        <div>
          <div className="text-[13px] text-sub">Administrador</div>
          <div className="font-heading font-extrabold text-xl text-ink">{me?.nombre}</div>
        </div>
        <div className="w-[42px] h-[42px] rounded-full bg-ink flex items-center justify-center text-lg">🛡️</div>
      </div>

      {kpis && (
        <div className="mx-5 mt-2 inline-flex items-center gap-1.5 rounded-full bg-teal-soft text-teal-dark font-heading font-bold text-[11px] px-3 py-1">
          Alcance: {kpis.alcance}
        </div>
      )}

      <div className="mx-5 mt-3 grid grid-cols-2 gap-2.5">
        <Kpi label="Clínicas" value={kpis ? String(kpis.clinicas) : '—'} />
        <Kpi label="Pacientes" value={kpis ? String(kpis.pacientes) : '—'} />
        <Kpi label="Citas hoy" value={kpis ? String(kpis.citas_hoy) : '—'} />
        <Kpi label="Ingresos del mes" value={kpis ? `$${kpis.ingresos_mes.toLocaleString('es-MX')}` : '—'} />
      </div>

      <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Acceso total</div>
      <div className="px-5 pt-2.5 flex flex-col gap-2.5">
        {MODULES.map((m) => (
          <div
            key={m.id}
            onClick={() => navigate(`/admin/${m.id}`)}
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
        <Button onClick={() => { logout(); navigate('/'); }} variant="outline" className="w-full">Cerrar sesión</Button>
      </div>
    </div>
  );
}
