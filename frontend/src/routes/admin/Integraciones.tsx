import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import type { IntegracionesEstado } from '../../api/types';

const CONECTOR: Record<string, { icon: string; label: string }> = {
  whatsapp: { icon: '💬', label: 'WhatsApp / IA' },
  lab: { icon: '🧪', label: 'Laboratorio' },
  farmacia: { icon: '💊', label: 'Farmacia' },
  pago: { icon: '💳', label: 'Pasarela de pago' },
  mapas: { icon: '🗺️', label: 'Mapas' },
  push: { icon: '🔔', label: 'Notificaciones push' },
};

const EVENTO_LABEL: Record<string, string> = {
  whatsapp: 'WhatsApp', lab: 'Laboratorio', farmacia: 'Farmacia', pago: 'Pago', mapas: 'Mapas', push: 'Push',
};

export function Integraciones() {
  const navigate = useNavigate();
  const [data, setData] = useState<IntegracionesEstado | null>(null);

  const load = () => api.integraciones.estado().then(setData);
  useEffect(() => { load(); }, []);

  const toggle = async (id: string, activo: boolean) => {
    await api.admin.toggleIntegracion(id, !activo);
    await load();
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Integraciones" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12px] text-teal-dark">
          Conectores externos por clínica. Cada evento entrante/saliente queda asentado en la traza. Un conector apagado rechaza sus eventos.
        </div>

        <div className="font-heading font-bold text-[13px] text-ink px-1 pt-1">Conectores</div>
        {data?.conectores.map((c) => {
          const meta = CONECTOR[c.tipo] ?? { icon: '🔌', label: c.tipo };
          return (
            <div key={c.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3">
              <div className="w-10 h-10 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">{meta.icon}</div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-[14px] text-ink">{meta.label}</div>
                <div className="text-xs text-sub">{c.activo ? 'Habilitado' : 'Deshabilitado'}</div>
              </div>
              <button
                onClick={() => toggle(c.id, c.activo)}
                className={`w-12 h-7 rounded-full relative transition-colors shrink-0 ${c.activo ? 'bg-teal' : 'bg-[#D3DEDA]'}`}
                aria-label={c.activo ? 'Deshabilitar' : 'Habilitar'}
              >
                <span className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-all ${c.activo ? 'left-6' : 'left-1'}`} />
              </button>
            </div>
          );
        })}
        {data && data.conectores.length === 0 && <div className="text-sm text-sub">Sin conectores configurados.</div>}

        <div className="font-heading font-bold text-[13px] text-ink px-1 pt-3">Traza reciente</div>
        {data && data.eventos_recientes.length === 0 && <div className="text-[13px] text-sub px-1">Sin eventos aún.</div>}
        {data?.eventos_recientes.map((e, i) => (
          <div key={i} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-2.5">
            <div className="min-w-0">
              <div className="font-semibold text-[13px] text-ink">{EVENTO_LABEL[e.tipo] ?? e.tipo}</div>
              <div className="text-[11px] text-sub truncate">{e.direccion === 'inbound' ? '↓ entrante' : '↑ saliente'} · {e.ref ?? '—'}</div>
            </div>
            <div className="text-[11px] text-sub whitespace-nowrap">{e.estado} · {new Date(e.fecha).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
