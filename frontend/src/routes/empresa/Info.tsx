import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api } from '../../api/client';
import type { InfoEmpresa } from '../../api/types';

export function Info() {
  const navigate = useNavigate();
  const [info, setInfo] = useState<InfoEmpresa | null>(null);
  const [razon, setRazon] = useState('');
  const [responsable, setResponsable] = useState('');
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.empresa.info().then((i) => {
      setInfo(i);
      setRazon(i.razon_social);
      setResponsable(i.responsable_sanitario ?? '');
    });
  }, []);

  const guardar = async () => {
    setSaving(true);
    const updated = await api.empresa.editarInfo({ razon_social: razon, responsable_sanitario: responsable });
    setInfo(updated);
    setSaved(true);
    setSaving(false);
    setTimeout(() => setSaved(false), 2500);
  };

  if (!info) return <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Información de la empresa" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">Razón social</div>
          <input value={razon} onChange={(e) => setRazon(e.target.value)}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
        </div>
        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">Responsable sanitario</div>
          <input value={responsable} onChange={(e) => setResponsable(e.target.value)} placeholder="Nombre del responsable"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
        </div>
        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">País</div>
          <div className="rounded-xl border border-border bg-[#F2F6F5] px-3.5 py-3 text-sm text-sub">{info.pais}</div>
        </div>

        <div className="pt-1 font-heading font-bold text-[13px] text-ink">Sucursales / ubicaciones</div>
        {info.sucursales.map((s) => (
          <div key={s.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3">
            <div className="text-lg">📍</div>
            <div className="font-semibold text-[13.5px] text-ink">{s.nombre}</div>
          </div>
        ))}

        <Button onClick={guardar} disabled={saving} className="w-full mt-2">
          {saving ? 'Guardando…' : saved ? '✓ Guardado' : 'Guardar cambios'}
        </Button>
      </div>
    </div>
  );
}
