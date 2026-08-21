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
  const [logo, setLogo] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);
  const [logoError, setLogoError] = useState<string | null>(null);

  useEffect(() => {
    api.empresa.info().then((i) => {
      setInfo(i);
      setRazon(i.razon_social);
      setResponsable(i.responsable_sanitario ?? '');
      setLogo(i.logo);
    });
  }, []);

  const onLogoFile = (file: File) => {
    setLogoError(null);
    if (file.size > 1_400_000) { setLogoError('Imagen muy pesada (máx ~1,4 MB).'); return; }
    const reader = new FileReader();
    reader.onload = () => setLogo(String(reader.result));
    reader.readAsDataURL(file);
  };

  const guardar = async () => {
    setSaving(true);
    const updated = await api.empresa.editarInfo({ razon_social: razon, responsable_sanitario: responsable, logo: logo ?? '' });
    setInfo(updated);
    setLogo(updated.logo);
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

        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">Logo de la clínica</div>
          <div className="rounded-2xl border border-border bg-white p-4 flex items-center gap-4">
            {logo ? (
              <img src={logo} alt="Logo" className="max-h-16 max-w-[120px] object-contain" />
            ) : (
              <div className="w-16 h-16 rounded-xl bg-[#F2F6F5] grid place-items-center text-2xl">🏥</div>
            )}
            <div className="flex-1 flex flex-col gap-2 items-start">
              <label className="text-[12.5px] font-semibold text-teal-dark cursor-pointer">
                {logo ? 'Cambiar logo' : 'Subir logo'}
                <input type="file" accept="image/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onLogoFile(f); }} />
              </label>
              {logo && <button onClick={() => setLogo(null)} className="text-[11.5px] font-semibold text-danger">Quitar</button>}
              <div className="text-[10.5px] text-sub">Se estampa en presupuestos y documentos.</div>
            </div>
          </div>
          {logoError && <div className="text-xs text-danger mt-1">{logoError}</div>}
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
