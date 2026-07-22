import { useEffect, useState } from 'react';
import { ScreenHeader } from '../../components/ScreenHeader';
import { Button } from '../../components/Button';
import { api } from '../../api/client';
import type { Medicamento } from '../../api/types';

export function Farmacia() {
  const [medicamentos, setMedicamentos] = useState<Medicamento[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.farmacia.medicamentos().then((m) => {
      setMedicamentos(m);
      setLoading(false);
    });
  }, []);

  return (
    <div className="h-full flex flex-col">
      <ScreenHeader title="Farmacia" subtitle="Tus medicamentos recetados" />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-2.5 pb-[90px] flex flex-col gap-2.5">
        {!loading && medicamentos.length === 0 && (
          <div className="text-center text-sm text-sub py-8">Aún no tienes medicamentos recetados.</div>
        )}
        {medicamentos.map((m, i) => (
          <div key={i} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">💊</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{m.nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{m.cantidad}</div>
            </div>
            {m.precio != null && <div className="font-heading font-bold text-sm text-ink">${m.precio}</div>}
          </div>
        ))}

        {medicamentos.length > 0 && <Button className="w-full mt-1">Enviar pedido por WhatsApp</Button>}

        <div className="mt-1.5 flex items-center gap-2.5 rounded-2xl bg-[#F2F6F5] p-3.5">
          <span className="text-lg">📍</span>
          <span className="text-[12.5px] leading-snug text-sub">Farmacia más cercana: a 800 m de tu ubicación</span>
        </div>
      </div>
    </div>
  );
}
