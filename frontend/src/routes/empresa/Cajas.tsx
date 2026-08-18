import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import { money } from '../../lib/citas';
import type { Caja, CajaDetalle } from '../../api/types';

const MEDIOS = [
  { id: 'efectivo', label: 'Efectivo' },
  { id: 'debito', label: 'Débito' },
  { id: 'credito', label: 'Crédito' },
  { id: 'transferencia', label: 'Transferencia' },
  { id: 'convenio', label: 'Convenio' },
  { id: 'otro', label: 'Otro' },
];
const medioLabel = (id: string) => MEDIOS.find((m) => m.id === id)?.label ?? id;
const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
const horaCorta = (iso: string) => new Date(iso).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });

export function Cajas() {
  const navigate = useNavigate();
  const [mi, setMi] = useState<CajaDetalle | null>(null);
  const [lista, setLista] = useState<Caja[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [detalle, setDetalle] = useState<CajaDetalle | null>(null);
  const [sheet, setSheet] = useState<null | 'abrir' | 'pago' | 'gasto' | 'cerrar'>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  // formularios
  const [abono, setAbono] = useState('');
  const [mov, setMov] = useState({ medio: 'efectivo', monto: '', convenio: '', boleta: '', glosa: '', emitir_boleta: false, exento: false });
  const [fondo, setFondo] = useState('');
  const [anularId, setAnularId] = useState<string | null>(null);
  const [anularMotivo, setAnularMotivo] = useState('');

  const load = async () => {
    const [m, l] = await Promise.all([api.cajas.miCaja(), api.cajas.lista()]);
    setMi(m);
    setLista(l);
    setLoaded(true);
  };
  useEffect(() => { load(); }, []);

  const abrir = async () => {
    setSaving(true); setError(null);
    try {
      await api.cajas.abrir(Number(abono) || 0);
      setSheet(null); setAbono('');
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo abrir la caja'); }
    finally { setSaving(false); }
  };

  const registrar = async (tipo: 'pago' | 'gasto') => {
    if (!mi) return;
    setSaving(true); setError(null);
    try {
      await api.cajas.movimiento(mi.id, {
        tipo, medio: mov.medio, monto: Number(mov.monto) || 0,
        convenio: mov.convenio || undefined, boleta: mov.boleta || undefined, glosa: mov.glosa || undefined,
        emitir_boleta: tipo === 'pago' ? mov.emitir_boleta : undefined,
        exento: tipo === 'pago' && mov.emitir_boleta ? mov.exento : undefined,
      });
      setSheet(null); setMov({ medio: 'efectivo', monto: '', convenio: '', boleta: '', glosa: '', emitir_boleta: false, exento: false });
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo registrar'); }
    finally { setSaving(false); }
  };

  const cerrar = async () => {
    if (!mi) return;
    setSaving(true); setError(null);
    try {
      await api.cajas.cerrar(mi.id, Number(fondo) || 0);
      setSheet(null); setFondo('');
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo cerrar la caja'); }
    finally { setSaving(false); }
  };

  const anular = async () => {
    if (!anularId) return;
    setSaving(true); setError(null);
    try {
      await api.cajas.anularPago(anularId, anularMotivo || undefined);
      setAnularId(null); setAnularMotivo('');
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo anular el pago'); }
    finally { setSaving(false); }
  };

  const cerradas = lista.filter((c) => c.estado === 'cerrada');

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Cajas" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-3">

        {/* Mi caja */}
        {loaded && !mi && (
          <div className="rounded-2xl border border-border bg-white px-4 py-5 text-center">
            <div className="text-[13px] text-sub">No tienes una caja abierta.</div>
            <Button onClick={() => { setSheet('abrir'); setError(null); }} className="mt-3">Abrir caja</Button>
          </div>
        )}

        {mi && (
          <div className="rounded-2xl border-[1.5px] border-teal bg-teal-soft px-4 py-4">
            <div className="flex items-center justify-between">
              <div className="text-[12px] font-semibold text-teal-dark">Mi caja abierta</div>
              <StatusTag label="Abierta" tone="teal" />
            </div>
            <div className="mt-1 font-heading font-extrabold text-[30px] text-ink tabular-nums">{money(mi.total)}</div>
            <div className="text-[11px] text-sub">saldo inicial {money(mi.abono_inicial)} + recaudado {money(mi.recaudado)} − gastos {money(mi.gastos)}</div>

            {Object.keys(mi.por_medio).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {Object.entries(mi.por_medio).map(([medio, monto]) => (
                  <span key={medio} className="rounded-full bg-white border border-[#CDEEE1] text-[11px] font-semibold text-teal-dark px-2.5 py-1">
                    {medioLabel(medio)}: {money(monto)}
                  </span>
                ))}
              </div>
            )}

            <div className="mt-3 grid grid-cols-3 gap-2">
              <Button onClick={() => { setSheet('pago'); setError(null); }} className="text-[12.5px] py-2">+ Pago</Button>
              <Button onClick={() => { setSheet('gasto'); setError(null); }} variant="outline" className="text-[12.5px] py-2">+ Gasto</Button>
              <Button onClick={() => { setSheet('cerrar'); setError(null); }} variant="ghost" className="text-[12.5px] py-2">Cerrar</Button>
            </div>
          </div>
        )}

        {/* Transacciones de mi caja */}
        {mi && mi.transacciones.length > 0 && (
          <div className="rounded-2xl border border-border bg-white">
            <div className="px-4 pt-3 pb-1 text-[12px] font-semibold text-ink">Movimientos de hoy</div>
            {mi.transacciones.map((t) => (
              <div key={t.id} className="flex items-center justify-between px-4 py-2.5 border-t border-[#F2F6F5]">
                <div className="min-w-0">
                  <div className="text-[13px] text-ink truncate">
                    {t.tipo === 'gasto' ? '🔻 ' : ''}{medioLabel(t.medio)}{t.convenio ? ` · ${t.convenio}` : ''}{t.paciente_nombre ? ` · ${t.paciente_nombre}` : ''}
                  </div>
                  <div className="text-[11px] text-sub">{horaCorta(t.fecha)}{t.boleta ? ` · boleta ${t.boleta}` : ''}{t.glosa ? ` · ${t.glosa}` : ''}</div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className={`text-[13px] font-semibold tabular-nums ${t.tipo === 'gasto' ? 'text-danger' : 'text-teal-dark'}`}>
                    {t.tipo === 'gasto' ? '−' : '+'}{money(t.monto)}
                  </div>
                  <button onClick={() => { setError(null); setAnularMotivo(''); setAnularId(t.id); }} className="text-[11px] font-bold text-danger">Anular</button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Cajas cerradas */}
        <div className="px-1 pt-2 text-[13px] font-heading font-bold text-ink">Cajas cerradas</div>
        {cerradas.length === 0 && <div className="text-center text-sm text-sub py-4">Aún no hay cajas cerradas.</div>}
        {cerradas.map((c) => (
          <button key={c.id} onClick={() => api.cajas.detalle(c.id).then(setDetalle)} className="text-left rounded-2xl border border-border bg-white px-4 py-3 flex items-center justify-between">
            <div>
              <div className="text-[13.5px] font-semibold text-ink">{c.responsable_nombre}</div>
              <div className="text-[11px] text-sub">{fechaCorta(c.abierta_at)} · recaudado {money(c.recaudado)}</div>
            </div>
            <div className="text-right">
              <div className="text-[13px] font-semibold text-ink tabular-nums">{money(c.total)}</div>
              <div className="text-[10px] text-sub">ver detalle ›</div>
            </div>
          </button>
        ))}
      </div>

      {/* Sheet: abrir */}
      {anularId && (
        <BottomSheet onClose={() => setAnularId(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Anular pago</div>
          <div className="text-[12.5px] text-sub">El pago sale de los totales de la caja y queda registrado como anulado, con tu nombre y la hora. No se borra.</div>
          <input value={anularMotivo} onChange={(e) => setAnularMotivo(e.target.value)} placeholder="Motivo (ej. cobro duplicado)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={anular} disabled={saving} className="w-full">{saving ? 'Anulando…' : 'Anular pago'}</Button>
        </BottomSheet>
      )}

      {sheet === 'abrir' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Abrir caja</div>
          <div className="text-[12.5px] text-sub">Ingresa el monto con el que abres la caja (fondo inicial).</div>
          <input value={abono} onChange={(e) => setAbono(e.target.value)} placeholder="Abono inicial" inputMode="numeric"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={abrir} disabled={saving} className="w-full">{saving ? 'Abriendo…' : 'Abrir caja'}</Button>
        </BottomSheet>
      )}

      {/* Sheet: pago / gasto */}
      {(sheet === 'pago' || sheet === 'gasto') && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">{sheet === 'pago' ? 'Registrar pago' : 'Registrar gasto'}</div>
          {sheet === 'pago' && (
            <select value={mov.medio} onChange={(e) => setMov((p) => ({ ...p, medio: e.target.value }))}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              {MEDIOS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
            </select>
          )}
          <input value={mov.monto} onChange={(e) => setMov((p) => ({ ...p, monto: e.target.value }))} placeholder="Monto" inputMode="numeric"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {sheet === 'pago' ? (
            <div className="flex gap-2">
              <input value={mov.convenio} onChange={(e) => setMov((p) => ({ ...p, convenio: e.target.value }))} placeholder="Convenio (Fonasa, Isapre…)"
                className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <input value={mov.boleta} onChange={(e) => setMov((p) => ({ ...p, boleta: e.target.value }))} placeholder="N° boleta"
                className="w-28 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            </div>
          ) : null}
          {sheet === 'pago' && (
            <label className="flex items-center gap-2 text-[12.5px] text-ink">
              <input type="checkbox" checked={mov.emitir_boleta} onChange={(e) => setMov((p) => ({ ...p, emitir_boleta: e.target.checked }))} className="accent-teal" />
              Emitir documento tributario (boleta SII / Nota Fiscal) por este pago
            </label>
          )}
          {sheet === 'pago' && mov.emitir_boleta && (
            <label className="flex items-center gap-2 text-[12.5px] text-ink pl-6">
              <input type="checkbox" checked={mov.exento} onChange={(e) => setMov((p) => ({ ...p, exento: e.target.checked }))} className="accent-teal" />
              Prestación exenta de IVA (médica/odontológica)
            </label>
          )}
          {sheet === 'gasto' && (
            <input value={mov.glosa} onChange={(e) => setMov((p) => ({ ...p, glosa: e.target.value }))} placeholder="Descripción del gasto"
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          )}
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={() => registrar(sheet)} disabled={saving || !mov.monto} className="w-full">{saving ? 'Guardando…' : 'Registrar'}</Button>
        </BottomSheet>
      )}

      {/* Sheet: cerrar */}
      {sheet === 'cerrar' && mi && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Cerrar caja</div>
          <div className="rounded-xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12.5px] text-teal-dark">
            Total de la caja: <strong>{money(mi.total)}</strong> · recaudado {money(mi.recaudado)} · gastos {money(mi.gastos)}.
          </div>
          <input value={fondo} onChange={(e) => setFondo(e.target.value)} placeholder="Efectivo que queda en caja (fondo fijo)" inputMode="numeric"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={cerrar} disabled={saving} className="w-full">{saving ? 'Cerrando…' : 'Cerrar caja'}</Button>
        </BottomSheet>
      )}

      {/* Sheet: detalle de una caja cerrada */}
      {detalle && (
        <BottomSheet onClose={() => setDetalle(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Caja de {detalle.responsable_nombre}</div>
          <div className="text-[12.5px] text-sub">{fechaCorta(detalle.abierta_at)}{detalle.cerrada_at ? ` — cerrada ${fechaCorta(detalle.cerrada_at)}` : ''}</div>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Recaudado</div><div className="font-bold text-ink tabular-nums">{money(detalle.recaudado)}</div></div>
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Gastos</div><div className="font-bold text-danger tabular-nums">{money(detalle.gastos)}</div></div>
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Fondo fijo</div><div className="font-bold text-ink tabular-nums">{money(detalle.fondo_fijo)}</div></div>
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Total</div><div className="font-bold text-teal-dark tabular-nums">{money(detalle.total)}</div></div>
          </div>
          {detalle.transacciones.length > 0 && (
            <div className="max-h-56 overflow-y-auto scrollhide">
              {detalle.transacciones.map((t) => (
                <div key={t.id} className="flex justify-between py-1.5 text-[12.5px] border-b border-[#F2F6F5]">
                  <span className="text-sub">{medioLabel(t.medio)}{t.paciente_nombre ? ` · ${t.paciente_nombre}` : ''}</span>
                  <span className={t.tipo === 'gasto' ? 'text-danger' : 'text-teal-dark'}>{t.tipo === 'gasto' ? '−' : '+'}{money(t.monto)}</span>
                </div>
              ))}
            </div>
          )}
          <Button onClick={() => setDetalle(null)} variant="ghost" className="w-full">Cerrar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
