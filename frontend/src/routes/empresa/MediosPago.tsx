import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api } from '../../api/client';
import type { MedioPago } from '../../api/types';

export function MediosPago() {
  const navigate = useNavigate();
  const [medios, setMedios] = useState<MedioPago[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [retencion, setRetencion] = useState('0'); // en %
  const [facturable, setFacturable] = useState(true);
  const [devolucion, setDevolucion] = useState(false);
  const [cuotas, setCuotas] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () => api.empresa.mediosPago().then(setMedios);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    await api.empresa.crearMedioPago({
      nombre, retencion_pct: Number(retencion) / 100, facturable, permite_devolucion: devolucion, acepta_cuotas: cuotas,
    });
    setNombre(''); setRetencion('0'); setFacturable(true); setDevolucion(false); setCuotas(false);
    setOpen(false);
    await load();
    setSaving(false);
  };

  const toggleActivo = async (m: MedioPago) => { await api.empresa.editarMedioPago(m.id, { activo: !m.activo }); await load(); };
  const eliminar = async (id: string) => { await api.empresa.eliminarMedioPago(id); await load(); };

  const chip = (on: boolean, label: string) => (
    <span className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${on ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>{label}</span>
  );

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Medios de pago" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {medios.length === 0 && <div className="text-center text-sm text-sub py-8">Sin medios de pago. Crea el primero (Efectivo, Débito, Crédito…).</div>}
        {medios.map((m) => (
          <div key={m.id} className={`rounded-2xl border border-border bg-white px-4 py-3.5 ${m.activo ? '' : 'opacity-60'}`}>
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{m.nombre}</div>
                <div className="mt-0.5 text-xs text-sub">Retención {(m.retencion_pct * 100).toFixed(m.retencion_pct * 100 % 1 ? 2 : 0)}%</div>
              </div>
              <button onClick={() => toggleActivo(m)}
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${m.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                {m.activo ? 'Activo' : 'Inactivo'}
              </button>
              <div onClick={() => eliminar(m.id)} className="cursor-pointer text-[13px] font-bold text-danger">Baja</div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {chip(m.facturable, m.facturable ? 'Facturable' : 'No facturable')}
              {m.permite_devolucion && chip(true, 'Devolución')}
              {m.acepta_cuotas && chip(true, 'Cuotas')}
            </div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nuevo medio de pago</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo medio de pago</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Crédito, Bono Fonasa)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="font-heading font-semibold text-xs text-sub">Retención (%) — comisión del banco/tarjeta</label>
          <input value={retencion} onChange={(e) => setRetencion(e.target.value)} inputMode="decimal" placeholder="ej. 2"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={facturable} onChange={(e) => setFacturable(e.target.checked)} className="accent-teal" />
            Facturable (genera documento tributario)
          </label>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={devolucion} onChange={(e) => setDevolucion(e.target.checked)} className="accent-teal" />
            Permite devolución (reembolsos)
          </label>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={cuotas} onChange={(e) => setCuotas(e.target.checked)} className="accent-teal" />
            Acepta cuotas / pagos diferidos
          </label>
          <Button onClick={crear} disabled={!nombre || saving} className="w-full">{saving ? 'Guardando…' : 'Crear medio'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}
