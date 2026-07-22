import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { StatusTag } from '../../components/ListRow';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { CitaMedico } from '../../api/types';

const ESTADO: Record<string, { label: string; tone: 'teal' | 'warn' }> = {
  confirmada: { label: 'Confirmada', tone: 'warn' },
  completada: { label: 'Atendida', tone: 'teal' },
  cancelada: { label: 'Cancelada', tone: 'warn' },
  no_show: { label: 'No asistió', tone: 'warn' },
};

export function Agenda() {
  const navigate = useNavigate();
  const { me } = useAuth();
  const [citas, setCitas] = useState<CitaMedico[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.medico.agenda().then((c) => {
      setCitas(c);
      setLoading(false);
    });
  }, []);

  return (
    <div className="h-full overflow-y-auto scrollhide pb-[90px]">
      <div className="px-[22px] pt-5 pb-1">
        <div className="text-[13px] text-sub">Hola,</div>
        <div className="font-heading font-extrabold text-xl text-ink">{me?.nombre}</div>
      </div>
      <ScreenHeader title="Agenda del día" subtitle="Tus citas y telemedicina de hoy" />
      <div className="px-5 pt-2.5 flex flex-col gap-2.5">
        {!loading && citas.length === 0 && <div className="text-center text-sm text-sub py-10">Sin citas hoy.</div>}
        {citas.map((c) => (
          <div
            key={c.id}
            onClick={() => navigate(`/medico/cita/${c.id}`)}
            className="flex items-center gap-3.5 bg-white border border-border rounded-2xl px-4 py-3.5 cursor-pointer"
          >
            <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0 font-heading font-bold text-teal-dark">
              {new Date(c.inicio).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-[14.5px] text-ink">{c.paciente_nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{c.servicio_nombre}</div>
            </div>
            <div className="flex flex-col items-end gap-1">
              <StatusTag {...ESTADO[c.estado] ?? { label: c.estado, tone: 'warn' }} />
              {c.atendida && <span className="text-[10px] text-teal font-heading font-bold">✓ atendida</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
