import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { Afiliado } from '../../api/types';

export function Padron() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Afiliado[]>([]);
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState<Afiliado | null>(null);
  const [f, setF] = useState({ documento_identidad: '', plan_cobertura: '', vigencia_hasta: '' });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.aseguradora.afiliados().then(setRows);
  useEffect(() => { load(); }, []);

  const alta = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.aseguradora.altaAfiliado({
        documento_identidad: f.documento_identidad.trim(),
        plan_cobertura: f.plan_cobertura || undefined,
        vigencia_hasta: f.vigencia_hasta || undefined,
      });
      setOpen(false);
      setF({ documento_identidad: '', plan_cobertura: '', vigencia_hasta: '' });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo dar de alta');
    } finally {
      setSaving(false);
    }
  };

  const baja = async () => {
    if (!confirm) return;
    await api.aseguradora.bajaAfiliado(confirm.affiliate_id);
    setConfirm(null);
    await load();
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Padrón de afiliados" onBack={() => navigate('/aseguradora')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {rows.length === 0 && <div className="text-center text-sm text-sub py-8">Padrón vacío.</div>}
        {rows.map((a) => (
          <div key={a.affiliate_id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{a.nombre ?? a.documento_identidad}</div>
                <div className="mt-0.5 text-xs text-sub truncate">{a.documento_identidad}{a.plan_cobertura ? ` · ${a.plan_cobertura}` : ''}</div>
              </div>
              <StatusTag label={a.vigente ? 'Vigente' : 'Sin vigencia'} tone={a.vigente ? 'teal' : 'warn'} />
            </div>
            <div className="mt-3">
              <Button onClick={() => setConfirm(a)} variant="outline" className="text-[13px] py-2.5 px-4">Dar de baja</Button>
            </div>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => { setOpen(true); setError(null); }} className="w-full">+ Alta de afiliado</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Alta de afiliado</div>
          <input value={f.documento_identidad} onChange={(e) => setF((p) => ({ ...p, documento_identidad: e.target.value }))} placeholder="Documento de identidad"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={f.plan_cobertura} onChange={(e) => setF((p) => ({ ...p, plan_cobertura: e.target.value }))} placeholder="Plan de cobertura"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={f.vigencia_hasta} onChange={(e) => setF((p) => ({ ...p, vigencia_hasta: e.target.value }))} placeholder="Vigencia hasta (YYYY-MM-DD)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={alta} disabled={saving || !f.documento_identidad} className="w-full">{saving ? 'Guardando…' : 'Dar de alta'}</Button>
        </BottomSheet>
      )}

      {confirm && (
        <BottomSheet onClose={() => setConfirm(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">¿Dar de baja "{confirm.nombre ?? confirm.documento_identidad}"?</div>
          <div className="text-[13px] leading-relaxed text-sub">Es una baja lógica: el afiliado deja de estar vigente pero se conserva su histórico.</div>
          <Button onClick={baja} className="w-full" style={{ background: 'var(--color-danger)' }}>Sí, dar de baja</Button>
          <Button onClick={() => setConfirm(null)} variant="ghost" className="w-full">Cancelar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
