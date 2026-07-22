import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { Promocion } from '../../api/types';

export function Promociones() {
  const navigate = useNavigate();
  const [promos, setPromos] = useState<Promocion[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [descuento, setDescuento] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => api.empresa.promociones().then(setPromos);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    await api.empresa.crearPromo({ nombre, descuento, estado: 'Borrador' });
    setNombre(''); setDescuento('');
    setOpen(false);
    await load();
    setSaving(false);
  };

  const toggle = async (p: Promocion) => {
    await api.empresa.editarPromo(p.id, { estado: p.estado === 'Activa' ? 'Borrador' : 'Activa' });
    await load();
  };

  const eliminar = async (id: string) => {
    await api.empresa.eliminarPromo(id);
    await load();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Promociones" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {promos.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no tienes promociones.</div>}
        {promos.map((p) => (
          <div key={p.id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{p.nombre}</div>
                <div className="mt-0.5 text-xs text-sub">{p.descuento}{p.segmento ? ` · ${p.segmento}` : ''}</div>
              </div>
              <StatusTag label={p.estado} tone={p.estado === 'Activa' ? 'teal' : 'warn'} />
            </div>
            <div className="flex gap-2 mt-3">
              <Button onClick={() => toggle(p)} variant="ghost" className="flex-1 text-[13px] py-2.5">
                {p.estado === 'Activa' ? 'Pausar' : 'Activar'}
              </Button>
              <Button onClick={() => eliminar(p.id)} variant="outline" className="text-[13px] py-2.5 px-4">Eliminar</Button>
            </div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nueva promoción</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva promoción</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre / oferta"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={descuento} onChange={(e) => setDescuento(e.target.value)} placeholder="Descuento (ej. -20%)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <Button onClick={crear} disabled={!nombre || saving} className="w-full">
            {saving ? 'Guardando…' : 'Crear como borrador'}
          </Button>
        </BottomSheet>
      )}
    </div>
  );
}
