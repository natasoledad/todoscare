import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api } from '../../api/client';
import type { ServicioAdmin } from '../../api/types';

export function Servicios() {
  const navigate = useNavigate();
  const [servicios, setServicios] = useState<ServicioAdmin[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [precio, setPrecio] = useState('');
  const [duracion, setDuracion] = useState('30');
  const [afectoIva, setAfectoIva] = useState(false); // salud: por defecto exento (Chile)
  const [comisiona, setComisiona] = useState(true); // acción clínica comisiona; lab/insumos no
  const [saving, setSaving] = useState(false);

  const load = () => api.empresa.servicios().then(setServicios);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    await api.empresa.crearServicio({ nombre, precio: Number(precio), duracion_min: Number(duracion), afecto_iva: afectoIva, comisiona });
    setNombre(''); setPrecio(''); setDuracion('30'); setAfectoIva(false); setComisiona(true);
    setOpen(false);
    await load();
    setSaving(false);
  };

  const toggleIva = async (s: ServicioAdmin) => {
    await api.empresa.editarServicio(s.id, { afecto_iva: !s.afecto_iva });
    await load();
  };

  const toggleComisiona = async (s: ServicioAdmin) => {
    await api.empresa.editarServicio(s.id, { comisiona: !s.comisiona });
    await load();
  };

  const eliminar = async (id: string) => {
    await api.empresa.eliminarServicio(id);
    await load();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Productos y servicios" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {servicios.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no tienes servicios. Crea el primero.</div>}
        {servicios.map((s) => (
          <div key={s.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{s.nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{s.duracion_min} min{s.specialty_nombre ? ` · ${s.specialty_nombre}` : ''}</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                <button onClick={() => toggleIva(s)}
                  className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${s.afecto_iva ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                  {s.afecto_iva ? 'Afecto a IVA' : 'Exento de IVA'}
                </button>
                <button onClick={() => toggleComisiona(s)}
                  className={`rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${s.comisiona ? 'bg-teal-soft text-teal-dark' : 'bg-[#EEF2F1] text-sub'}`}>
                  {s.comisiona ? 'Comisiona' : 'No comisiona'}
                </button>
              </div>
            </div>
            <div className="font-heading font-bold text-sm text-ink tabular-nums">${s.precio}</div>
            <div onClick={() => eliminar(s.id)} className="cursor-pointer text-[13px] font-bold text-danger ml-1">Baja</div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nuevo servicio</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo servicio</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del servicio"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <input value={precio} onChange={(e) => setPrecio(e.target.value)} placeholder="Precio" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={duracion} onChange={(e) => setDuracion(e.target.value)} placeholder="Duración (min)" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={afectoIva} onChange={(e) => setAfectoIva(e.target.checked)} className="accent-teal" />
            Afecto a IVA (las prestaciones médicas/odontológicas van exentas)
          </label>
          <label className="flex items-center gap-2 text-[12.5px] text-ink">
            <input type="checkbox" checked={comisiona} onChange={(e) => setComisiona(e.target.checked)} className="accent-teal" />
            Comisiona al profesional (laboratorio e insumos: desmarcar)
          </label>
          <Button onClick={crear} disabled={!nombre || !precio || saving} className="w-full">
            {saving ? 'Guardando…' : 'Crear y activar'}
          </Button>
        </BottomSheet>
      )}
    </div>
  );
}
