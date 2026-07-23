import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { Autorizacion, FichaAfiliado } from '../../api/types';

const ESTADO_TONE: Record<string, 'teal' | 'warn'> = { aprobada: 'teal', rechazada: 'warn', pendiente: 'warn', pendiente_info: 'warn' };
const ESTADO_LABEL: Record<string, string> = { pendiente: 'Pendiente', aprobada: 'Aprobada', rechazada: 'Rechazada', pendiente_info: 'Falta info' };

export function Autorizaciones() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Autorizacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [sheet, setSheet] = useState<Autorizacion | null>(null);
  const [motivo, setMotivo] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ficha, setFicha] = useState<FichaAfiliado | null>(null);
  const [fichaErr, setFichaErr] = useState<string | null>(null);

  const load = () => api.aseguradora.autorizaciones().then((r) => { setRows(r); setLoading(false); });
  useEffect(() => { load(); }, []);

  const resolver = async (decision: 'aprobar' | 'rechazar' | 'pedir_info') => {
    if (!sheet) return;
    setBusy(true);
    setError(null);
    try {
      await api.aseguradora.resolver(sheet.authorization_id, decision, motivo || undefined);
      setSheet(null);
      setMotivo('');
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo resolver');
    } finally {
      setBusy(false);
    }
  };

  const verFicha = async (patientId: string) => {
    setFicha(null);
    setFichaErr(null);
    try {
      setFicha(await api.aseguradora.ficha(patientId));
    } catch (e) {
      setFichaErr(e instanceof ApiError ? String(e.detail) : 'No disponible');
    }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Autorizaciones" onBack={() => navigate('/aseguradora')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-2.5">
        {!loading && rows.length === 0 && <div className="text-center text-sm text-sub py-8">Sin autorizaciones pendientes.</div>}
        {rows.map((a) => (
          <div key={a.authorization_id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="font-semibold text-[14px] text-ink truncate">{a.paciente}</div>
                <div className="mt-0.5 text-xs text-sub truncate">{a.servicio} · {a.clinica}</div>
              </div>
              <StatusTag label={ESTADO_LABEL[a.estado] ?? a.estado} tone={ESTADO_TONE[a.estado] ?? 'warn'} />
            </div>
            {a.motivo_rechazo && <div className="mt-2 text-xs text-danger">Motivo: {a.motivo_rechazo}</div>}
            {a.estado === 'pendiente' || a.estado === 'pendiente_info' ? (
              <div className="mt-3">
                <Button onClick={() => { setSheet(a); setError(null); }} className="text-[13px] py-2.5 px-4">Resolver</Button>
              </div>
            ) : null}
          </div>
        ))}
      </div>

      {sheet && (
        <BottomSheet onClose={() => { setSheet(null); setFicha(null); setFichaErr(null); }}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Resolver autorización</div>
          <div className="text-[13px] text-sub">{sheet.paciente} · {sheet.servicio} · {sheet.clinica}</div>

          <button onClick={() => verFicha(sheet.patient_id)} className="text-left text-[13px] font-semibold text-teal underline">
            Ver dato clínico mínimo autorizado
          </button>
          {fichaErr && <div className="text-xs text-sub">🔒 {fichaErr}</div>}
          {ficha && (
            <div className="rounded-xl bg-teal-soft border border-[#CDEEE1] p-3 text-[12.5px] text-teal-dark">
              <div className="font-semibold">{ficha.nombre} · {ficha.plan_cobertura ?? 'sin plan'}</div>
              {ficha.prestaciones_autorizadas.map((p, i) => (
                <div key={i} className="mt-1">• {p.servicio}{p.diagnostico ? ` — ${p.diagnostico}` : ''}</div>
              ))}
            </div>
          )}

          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo (requerido para rechazar)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={() => resolver('aprobar')} disabled={busy} className="w-full">Aprobar</Button>
          <Button onClick={() => resolver('rechazar')} disabled={busy} variant="outline" className="w-full">Rechazar</Button>
          <Button onClick={() => resolver('pedir_info')} disabled={busy} variant="ghost" className="w-full">Pedir más información</Button>
        </BottomSheet>
      )}
    </div>
  );
}
