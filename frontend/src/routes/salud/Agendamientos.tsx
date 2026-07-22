import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { Cita } from '../../api/types';

const ESTADO_LABEL: Record<string, string> = {
  confirmada: 'Próxima',
  completada: 'Realizada',
  cancelada: 'Cancelada',
  no_show: 'No asistió',
};

export function Agendamientos() {
  const navigate = useNavigate();
  const [citas, setCitas] = useState<Cita[]>([]);

  useEffect(() => {
    api.agenda.mias().then(setCitas);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Agendamientos realizados" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-2.5">
        {citas.length === 0 && <div className="text-center text-sm text-sub py-6">Sin agendamientos todavía.</div>}
        {citas.map((c) => (
          <div key={c.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">🩺</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{c.servicio_nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{new Date(c.inicio).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })}</div>
            </div>
            <StatusTag label={ESTADO_LABEL[c.estado] || c.estado} tone={c.estado === 'confirmada' ? 'warn' : c.estado === 'completada' ? 'teal' : 'warn'} />
          </div>
        ))}
      </div>
    </div>
  );
}
