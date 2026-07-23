import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../../components/BackHeader';
import { Button } from '../../../components/Button';
import { BottomSheet } from '../../../components/BottomSheet';
import { api, ApiError } from '../../../api/client';
import type { CrmLiquidacion } from '../../../api/types';
import { money } from '../../crm/DetalleClinicaView';

export function Liquidaciones() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<CrmLiquidacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState<CrmLiquidacion | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.crm.liquidaciones().then((r) => { setRows(r); setLoading(false); });
  useEffect(() => { load(); }, []);

  const conciliar = async () => {
    if (!confirm) return;
    setBusy(true);
    setError(null);
    try {
      await api.crm.conciliar(confirm.split_id);
      setConfirm(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo conciliar');
    } finally {
      setBusy(false);
    }
  };

  const total = rows.reduce((a, r) => a + r.monto, 0);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Liquidaciones" onBack={() => navigate('/admin/crm')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3.5 text-[12.5px] text-teal-dark">
          Al conciliar se marca la liquidación como pagada y se asienta un egreso <strong>inmutable</strong> en el ledger.
        </div>
        {!loading && rows.length > 0 && (
          <div className="flex justify-between items-center px-1 py-1">
            <div className="text-[13px] text-sub">Total por liquidar</div>
            <div className="font-heading font-bold text-[15px] text-ink tabular-nums">{money(total)}</div>
          </div>
        )}
        {!loading && rows.length === 0 && <div className="text-center text-sm text-sub py-8">No hay liquidaciones pendientes. 🎉</div>}
        {rows.map((r) => (
          <div key={r.split_id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{r.prestador}</div>
                <div className="mt-0.5 text-xs text-sub truncate">{r.razon_social} · {new Date(r.fecha).toLocaleDateString('es-MX')}</div>
              </div>
              <div className="font-heading font-bold text-[15px] text-ink tabular-nums shrink-0">{money(r.monto)}</div>
            </div>
            <div className="mt-3">
              <Button onClick={() => setConfirm(r)} className="text-[13px] py-2.5 px-4">Conciliar y marcar pagado</Button>
            </div>
          </div>
        ))}
      </div>

      {confirm && (
        <BottomSheet onClose={() => setConfirm(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Conciliar liquidación</div>
          <div className="text-[13px] leading-relaxed text-sub">
            Vas a pagar {money(confirm.monto)} a <strong>{confirm.prestador}</strong> ({confirm.razon_social}). Esto
            asienta un egreso inmutable en el ledger y no se puede deshacer.
          </div>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={conciliar} disabled={busy} className="w-full">{busy ? 'Conciliando…' : `Sí, pagar ${money(confirm.monto)}`}</Button>
          <Button onClick={() => setConfirm(null)} variant="ghost" className="w-full">Cancelar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
