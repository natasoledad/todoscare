import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { Arancel, Convenio } from '../../api/types';

export function Convenios() {
  const navigate = useNavigate();
  const [convenios, setConvenios] = useState<Convenio[]>([]);
  const [open, setOpen] = useState<Convenio | null>(null);
  const [aranceles, setAranceles] = useState<Arancel[]>([]);
  const [sheet, setSheet] = useState(false);
  const [f, setF] = useState({ service_id: '', cobertura_pct: '80', copago: '0' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { api.aseguradora.convenios().then(setConvenios); }, []);

  const abrir = async (c: Convenio) => {
    setOpen(c);
    setAranceles(await api.aseguradora.aranceles(c.agreement_id));
  };

  const versionar = async () => {
    if (!open) return;
    setSaving(true);
    setError(null);
    try {
      await api.aseguradora.crearArancel(open.agreement_id, { service_id: f.service_id.trim(), cobertura_pct: Number(f.cobertura_pct), copago: Number(f.copago) });
      setSheet(false);
      setF({ service_id: '', cobertura_pct: '80', copago: '0' });
      setAranceles(await api.aseguradora.aranceles(open.agreement_id));
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo versionar el arancel');
    } finally {
      setSaving(false);
    }
  };

  // Detalle de un convenio (aranceles)
  if (open) {
    return (
      <div className="h-full flex flex-col relative">
        <BackHeader title={open.clinica} onBack={() => setOpen(null)} />
        <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
          <div className="text-[12px] text-sub">Aranceles del convenio · cobertura y copago por servicio</div>
          {aranceles.length === 0 && <div className="text-sm text-sub">Sin aranceles definidos.</div>}
          {aranceles.map((a) => (
            <div key={a.arancel_id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3.5">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{a.servicio}</div>
                <div className="mt-0.5 text-xs text-sub">Copago ${a.copago.toLocaleString('es-MX')}</div>
              </div>
              <div className="font-heading font-bold text-[15px] text-teal-dark tabular-nums">{a.cobertura_pct}%</div>
            </div>
          ))}
        </div>
        <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
          <Button onClick={() => { setSheet(true); setError(null); }} className="w-full">+ Versionar arancel</Button>
        </div>
        {sheet && (
          <BottomSheet onClose={() => setSheet(false)}>
            <div className="font-heading font-extrabold text-[17px] text-ink">Versionar arancel</div>
            <div className="text-[12.5px] text-sub">Al versionar, el arancel anterior de ese servicio se da de baja (histórico conservado) y entra el nuevo.</div>
            <input value={f.service_id} onChange={(e) => setF((p) => ({ ...p, service_id: e.target.value }))} placeholder="ID del servicio (catálogo de la clínica)"
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <div className="flex gap-2">
              <input value={f.cobertura_pct} onChange={(e) => setF((p) => ({ ...p, cobertura_pct: e.target.value }))} placeholder="Cobertura %" inputMode="numeric"
                className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <input value={f.copago} onChange={(e) => setF((p) => ({ ...p, copago: e.target.value }))} placeholder="Copago" inputMode="numeric"
                className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            </div>
            {error && <div className="text-xs text-danger">{error}</div>}
            <Button onClick={versionar} disabled={saving || !f.service_id} className="w-full">{saving ? 'Guardando…' : 'Publicar arancel'}</Button>
          </BottomSheet>
        )}
      </div>
    );
  }

  // Lista de convenios
  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Convenios y aranceles" onBack={() => navigate('/aseguradora')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        {convenios.length === 0 && <div className="text-center text-sm text-sub py-8">Sin convenios.</div>}
        {convenios.map((c) => (
          <div key={c.agreement_id} onClick={() => abrir(c)} className="rounded-2xl border border-border bg-white px-4 py-3.5 cursor-pointer">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-sm text-ink truncate">{c.clinica}</div>
                <div className="mt-0.5 text-xs text-sub">{c.aranceles} arancel(es){c.vigencia_fin ? ` · hasta ${new Date(c.vigencia_fin).toLocaleDateString('es-MX')}` : ''}</div>
              </div>
              <StatusTag label={c.vigente ? 'Vigente' : 'Vencido'} tone={c.vigente ? 'teal' : 'warn'} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
