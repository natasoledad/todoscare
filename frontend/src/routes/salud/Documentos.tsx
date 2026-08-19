import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import type { DocumentoPaciente } from '../../api/types';

const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });

/** Documentos clínicos del paciente: firma de consentimientos (64.8) y
 *  lectura de certificados. */
export function Documentos() {
  const navigate = useNavigate();
  const [docs, setDocs] = useState<DocumentoPaciente[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.salud.documentos().then(setDocs);
  useEffect(() => { load(); }, []);

  const firmar = async (id: string) => {
    setBusy(id); setError(null);
    try { await api.salud.firmarDocumento(id); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo firmar.'); }
    finally { setBusy(null); }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Documentos" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        {docs.length === 0 && <div className="text-center text-sm text-sub py-8">No tienes documentos por ahora.</div>}
        {docs.map((d) => (
          <div key={d.id} className="rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="flex items-center justify-between">
              <div className="font-semibold text-[14px] text-ink">{d.titulo}</div>
              <span className="text-[11px] text-sub">{fecha(d.fecha)}</span>
            </div>
            {d.contenido && <div className="mt-2 text-[12.5px] text-ink whitespace-pre-line leading-relaxed">{d.contenido}</div>}
            {d.requiere_firma ? (
              d.firmado_paciente ? (
                <div className="mt-2 inline-block rounded-full bg-teal-soft px-2.5 py-0.5 text-[11px] font-semibold text-teal-dark">
                  ✓ Firmado el {d.firmado_at ? fecha(d.firmado_at) : ''}
                </div>
              ) : (
                <div className="mt-2.5">
                  <div className="text-[11.5px] text-sub mb-1.5">Este documento requiere tu firma para continuar tu atención.</div>
                  <Button onClick={() => firmar(d.id)} disabled={busy === d.id} className="w-full">{busy === d.id ? 'Firmando…' : 'Firmar documento'}</Button>
                </div>
              )
            ) : null}
          </div>
        ))}
        {error && <div className="text-xs text-danger">{error}</div>}
      </div>
    </div>
  );
}
