import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { FichaPaciente } from '../../api/types';

const FICHA_LABELS: Record<string, string> = {
  fecha_nacimiento: 'Fecha de nacimiento',
  sexo: 'Sexo',
  grupo_sanguineo: 'Grupo sanguíneo',
  alergias: 'Alergias',
  medicacion_actual: 'Medicación actual',
  antecedentes: 'Antecedentes',
  contacto_emergencia: 'Contacto de emergencia',
  seguro: 'Seguro / Isapre',
};

export function Ficha() {
  const { patientId = '' } = useParams();
  const navigate = useNavigate();
  const [ficha, setFicha] = useState<FichaPaciente | null>(null);
  const [piezas, setPiezas] = useState<Record<string, { estado: string }>>({});

  useEffect(() => {
    api.medico.ficha(patientId).then((f) => {
      setFicha(f);
      setPiezas(f.odontograma || {});
    });
  }, [patientId]);

  const togglePieza = async (key: string) => {
    const current = piezas[key]?.estado === 'pendiente' ? 'tratada' : 'pendiente';
    const next = { ...piezas, [key]: { estado: current } };
    setPiezas(next);
    await api.medico.odontograma(patientId, next);
  };

  if (!ficha) return <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;

  const keys = Object.keys(piezas).length > 0 ? Object.keys(piezas) : Array.from({ length: 16 }, (_, i) => String(i));

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Ficha clínica" onBack={() => navigate(-1)} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-4">
        <div>
          <div className="font-heading font-extrabold text-lg text-ink">{ficha.nombre}</div>
          <div className="text-xs text-sub mt-0.5">RUT {ficha.rut} · Nivel {ficha.nivel}</div>
        </div>

        <div className="rounded-2xl border border-border bg-white px-1.5">
          {Object.entries(FICHA_LABELS).map(([key, label], i, arr) => (
            <div key={key} className={`flex justify-between px-2.5 py-3 ${i < arr.length - 1 ? 'border-b border-[#F2F6F5]' : ''}`}>
              <div className="text-[13px] text-sub">{label}</div>
              <div className="font-semibold text-[13px] text-ink text-right max-w-[60%]">{String(ficha.ficha[key] ?? '—')}</div>
            </div>
          ))}
        </div>

        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Exámenes</div>
          <div className="flex flex-col gap-2">
            {ficha.examenes.length === 0 && <div className="text-sm text-sub">Sin exámenes.</div>}
            {ficha.examenes.map((ex, i) => (
              <div key={i} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3">
                <div className="flex-1 min-w-0">
                  <div className="font-semibold text-[13.5px] text-ink truncate">{ex.nombre}</div>
                  <div className="text-xs text-sub">{new Date(ex.fecha).toLocaleDateString('es-MX')}</div>
                </div>
                <StatusTag label={ex.estado === 'listo' ? 'Listo' : ex.estado} tone={ex.estado === 'listo' ? 'teal' : 'warn'} />
              </div>
            ))}
          </div>
        </div>

        {ficha.hospitalizaciones.length > 0 && (
          <div>
            <div className="font-heading font-bold text-[13px] text-ink mb-2">Hospitalizaciones</div>
            <div className="flex flex-col gap-2">
              {ficha.hospitalizaciones.map((h, i) => (
                <div key={i} className="rounded-2xl border border-border bg-white px-4 py-3 text-[13px]">
                  <span className="font-semibold text-ink">{h.motivo}</span>
                  <span className="text-sub"> · {h.centro}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Odontograma</div>
          <div className="text-[11.5px] text-sub mb-2">Toca una pieza para alternar pendiente / tratada.</div>
          <div className="bg-white border border-border rounded-2xl p-4 grid grid-cols-8 gap-1.5">
            {keys.map((k) => (
              <div
                key={k}
                onClick={() => togglePieza(k)}
                className={`aspect-square rounded-md border border-border-strong cursor-pointer ${
                  piezas[k]?.estado === 'pendiente' ? 'bg-[#F6D9CF]' : piezas[k]?.estado === 'tratada' ? 'bg-teal-soft' : 'bg-[#F2F6F5]'
                }`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
