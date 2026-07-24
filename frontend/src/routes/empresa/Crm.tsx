import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api } from '../../api/client';
import type { CrmDetalleClinica } from '../../api/types';
import { DetalleClinicaView } from '../crm/DetalleClinicaView';

export function Crm() {
  const navigate = useNavigate();
  const [d, setD] = useState<CrmDetalleClinica | null>(null);

  useEffect(() => {
    api.crm.miClinica().then(setD);
  }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Indicadores (CRM)" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8">
        {d ? (
          <>
            <div className="text-[11px] text-sub pb-3">{d.razon_social} · Período {d.period}</div>
            <DetalleClinicaView d={d} />
            <div className="pt-3">
              <Button onClick={() => navigate('/empresa/campanas')} variant="outline" className="w-full">📣 Marketing digital · Campañas</Button>
            </div>
          </>
        ) : (
          <div className="text-center text-sm text-sub py-8">Cargando…</div>
        )}
      </div>
    </div>
  );
}
