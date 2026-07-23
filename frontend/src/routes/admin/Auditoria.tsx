import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import type { AuditEntry } from '../../api/types';

const ACCION_LABEL: Record<string, string> = {
  ver_ficha_clinica: 'Consultó ficha clínica',
  crear_prontuario: 'Registró prontuario',
  enmendar_prontuario: 'Enmendó prontuario',
  firmar_prescripcion: 'Firmó prescripción',
  reemitir_prescripcion: 'Reemitió prescripción',
  crear_orden_examen: 'Creó orden de examen',
  actualizar_odontograma: 'Actualizó odontograma',
  cerrar_atencion: 'Cerró atención',
  no_show: 'Marcó no-show',
};

export function Auditoria() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.admin.auditoria().then((r) => { setRows(r); setLoading(false); });
  }, []);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Auditoría" onBack={() => navigate('/admin')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3.5 text-[12.5px] text-teal-dark">
          🔒 Registro inmutable de accesos y cambios — solo metadatos. El contenido clínico nunca es visible para el
          administrador.
        </div>
        {!loading && rows.length === 0 && <div className="text-center text-sm text-sub py-8">Sin registros de auditoría.</div>}
        {rows.map((r, i) => (
          <div key={i} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex justify-between items-start gap-2">
              <div className="font-semibold text-[13px] text-ink">{ACCION_LABEL[r.accion] ?? r.accion}</div>
              <div className="text-[11px] text-sub whitespace-nowrap">{new Date(r.fecha).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })}</div>
            </div>
            <div className="mt-0.5 text-xs text-sub">{r.actor ?? 'Sistema'} · {r.recurso}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
