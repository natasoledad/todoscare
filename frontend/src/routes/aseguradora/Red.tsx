import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { RedClinica } from '../../api/types';

export function Red() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<RedClinica[]>([]);

  useEffect(() => { api.aseguradora.red().then(setRows); }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Red de prestadores" onBack={() => navigate('/aseguradora')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        <div className="text-[12px] text-sub">Clínicas con convenio con esta aseguradora.</div>
        {rows.length === 0 && <div className="text-center text-sm text-sub py-8">Sin clínicas en red.</div>}
        {rows.map((c) => (
          <div key={c.clinic_id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="min-w-0">
              <div className="font-semibold text-[14px] text-ink truncate">{c.clinica}</div>
              <div className="mt-0.5 text-xs text-sub">{c.pais}</div>
            </div>
            <StatusTag label={c.vigente ? 'Vigente' : 'Vencido'} tone={c.vigente ? 'teal' : 'warn'} />
          </div>
        ))}
      </div>
    </div>
  );
}
