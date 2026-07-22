import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { useAuth } from '../../context/AuthContext';
import { api, ApiError } from '../../api/client';
import type { Movimiento, Wallet as WalletBalance } from '../../api/types';

export function Wallet() {
  const navigate = useNavigate();
  const { refreshMe } = useAuth();
  const [balance, setBalance] = useState<WalletBalance | null>(null);
  const [movimientos, setMovimientos] = useState<Movimiento[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    const [b, m] = await Promise.all([api.billetera.balance(), api.billetera.movimientos()]);
    setBalance(b);
    setMovimientos(m);
  };

  useEffect(() => {
    load();
  }, []);

  const pagarCashback = async () => {
    if (!balance) return;
    setError(null);
    try {
      await api.billetera.pagarCashback(Math.min(10, balance.cashback || 10));
      await load();
      await refreshMe();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo procesar el pago');
    }
  };

  const canjearPuntos = async () => {
    if (!balance) return;
    setError(null);
    try {
      await api.billetera.canjearPuntos(Math.min(100, balance.puntos));
      await load();
      await refreshMe();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo canjear');
    }
  };

  if (!balance) return null;

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Billetera TODOSCARE" onBack={() => navigate('/app/perfil')} />

      <div className="mx-5 mt-3.5 rounded-2xl p-[18px] text-white bg-gradient-to-br from-teal to-teal-dark">
        <div className="flex justify-between">
          <div>
            <div className="font-heading font-semibold text-[11px] uppercase tracking-wider opacity-85">Puntos</div>
            <div className="mt-1 font-heading font-extrabold text-2xl">{balance.puntos}</div>
          </div>
          <div className="text-right">
            <div className="font-heading font-semibold text-[11px] uppercase tracking-wider opacity-85">Cashback</div>
            <div className="mt-1 font-heading font-extrabold text-2xl">${balance.cashback.toFixed(2)}</div>
          </div>
        </div>
        <div className="mt-2.5 text-xs opacity-85">Usa tu cashback como pago en consultas, exámenes y farmacia.</div>
      </div>

      {error && <div className="mx-5 mt-2 text-xs text-danger">{error}</div>}

      <div className="mx-5 mt-3 grid grid-cols-2 gap-2.5">
        <Button onClick={pagarCashback} className="text-[13.5px] px-3 py-3">
          Pagar con cashback
        </Button>
        <Button onClick={canjearPuntos} variant="ghost" className="text-[13.5px] px-3 py-3">
          Canjear puntos
        </Button>
      </div>

      <div className="px-5 pt-[18px] font-heading font-bold text-[13px] text-ink">Movimientos</div>
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-2.5 pb-7 flex flex-col gap-2.5">
        {movimientos.length === 0 && <div className="text-center text-sm text-sub py-6">Sin movimientos todavía.</div>}
        {movimientos.map((tx, i) => (
          <div key={i} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-[15px] py-3.5">
            <div className="w-[38px] h-[38px] rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">
              {tx.tipo.includes('consulta') ? '🩺' : tx.tipo.includes('examen') ? '🧪' : tx.tipo.includes('cashback') ? '💳' : '🎁'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-[13.5px] text-ink">{tx.motivo || tx.tipo}</div>
              <div className="mt-0.5 text-[11.5px] text-sub">{new Date(tx.fecha).toLocaleDateString('es-MX')}</div>
            </div>
            <div className="text-right shrink-0">
              {tx.puntos != null && <div className={`font-heading font-bold text-[12.5px] ${tx.puntos < 0 ? 'text-danger' : 'text-teal'}`}>{tx.puntos > 0 ? '+' : ''}{tx.puntos} pts</div>}
              {tx.cashback != null && (
                <div className={`mt-0.5 font-semibold text-[11.5px] ${tx.cashback < 0 ? 'text-danger' : 'text-sub'}`}>
                  {tx.cashback > 0 ? '+' : ''}${tx.cashback.toFixed(2)}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
