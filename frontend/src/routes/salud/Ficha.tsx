import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { FichaUpdateInput, SugerenciaIA } from '../../api/types';

const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: 'numeric' });

/** Sugerencias de la IA clínica (72): al subir exámenes, la IA propone
 *  actualizar la ficha y un próximo control. El paciente confirma o descarta. */
function SugerenciasIA({ onApplied }: { onApplied: () => void }) {
  const [sugs, setSugs] = useState<SugerenciaIA[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => api.ia.sugerencias('pendiente').then(setSugs).catch(() => setSugs([]));
  useEffect(() => { load(); }, []);

  const aplicar = async (id: string) => {
    setBusy(id);
    try { await api.ia.aplicar(id); await load(); onApplied(); } finally { setBusy(null); }
  };
  const descartar = async (id: string) => {
    setBusy(id);
    try { await api.ia.descartar(id); await load(); } finally { setBusy(null); }
  };

  if (sugs.length === 0) return null;
  return (
    <div className="rounded-2xl border border-teal/40 bg-[#F0FBF7] p-3.5 flex flex-col gap-2.5">
      <div className="font-heading font-bold text-[13px] text-teal-dark">✨ Sugerencias de la IA</div>
      {sugs.map((s) => (
        <div key={s.id} className="rounded-xl bg-white border border-border px-3 py-2.5">
          <div className="text-[12.5px] text-ink leading-snug">{s.resumen}</div>
          {s.proximo_control && <div className="text-[11px] text-sub mt-0.5">Próximo control sugerido: {fechaCorta(s.proximo_control)}</div>}
          <div className="mt-2 flex gap-2">
            <Button onClick={() => aplicar(s.id)} disabled={busy === s.id} className="text-[12px] py-1.5 px-3">Aplicar a mi ficha</Button>
            <Button onClick={() => descartar(s.id)} disabled={busy === s.id} variant="outline" className="text-[12px] py-1.5 px-3">Descartar</Button>
          </div>
        </div>
      ))}
    </div>
  );
}

const FIELDS: { key: keyof FichaUpdateInput; label: string; placeholder: string }[] = [
  { key: 'fecha_nacimiento', label: 'Fecha de nacimiento', placeholder: 'AAAA-MM-DD' },
  { key: 'sexo', label: 'Sexo', placeholder: 'Femenino / Masculino / Otro' },
  { key: 'grupo_sanguineo', label: 'Grupo sanguíneo', placeholder: 'O+' },
  { key: 'alergias', label: 'Alergias', placeholder: 'Penicilina' },
  { key: 'medicacion_actual', label: 'Medicación actual', placeholder: 'Losartán 50mg diario' },
  { key: 'antecedentes', label: 'Antecedentes', placeholder: 'Hipertensión (2022)' },
  { key: 'contacto_emergencia', label: 'Contacto de emergencia', placeholder: 'Nombre y teléfono' },
  { key: 'seguro', label: 'Seguro / Isapre', placeholder: 'Nombre del seguro' },
];

export function Ficha() {
  const navigate = useNavigate();
  const { patient, refreshMe } = useAuth();
  const [values, setValues] = useState<FichaUpdateInput>(() => (patient?.ficha as FichaUpdateInput) || {});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedOk, setSavedOk] = useState(false);

  if (!patient) return null;

  const complete = FIELDS.every((f) => !!(values[f.key] as string | undefined)?.trim());

  const save = async () => {
    setSaving(true);
    setError(null);
    setSavedOk(false);
    try {
      await api.patients.updateFicha(values);
      await refreshMe();
      setSavedOk(true);
    } catch {
      setError('No se pudo guardar la ficha. Intenta nuevamente.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Ficha clínica" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        <SugerenciasIA onApplied={() => { refreshMe(); setValues((patient?.ficha as FichaUpdateInput) || {}); }} />
        {(values as Record<string, string>).proximo_control && (
          <div className="rounded-2xl border border-border bg-white p-3.5 text-[12.5px] text-ink">
            🗓️ Próximo control sugerido: <b>{fechaCorta((values as Record<string, string>).proximo_control)}</b>
          </div>
        )}
        {!complete && (
          <div className="rounded-2xl bg-warn-bg border border-warn-border p-3.5 text-xs leading-relaxed text-[#8A6A00]">
            ✨ Completa tu ficha al 100% y gana +300 pts.
          </div>
        )}
        {FIELDS.map((f) => (
          <div key={f.key}>
            <div className="mb-1.5 font-heading font-semibold text-xs text-sub">{f.label}</div>
            <input
              value={(values[f.key] as string) || ''}
              placeholder={f.placeholder}
              onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
            />
          </div>
        ))}
        {error && <div className="text-xs text-danger">{error}</div>}
        {savedOk && <div className="text-xs text-teal-dark font-semibold">✓ Ficha guardada.</div>}
        <Button onClick={save} disabled={saving} className="w-full mt-2">
          {saving ? 'Guardando…' : 'Guardar ficha'}
        </Button>
      </div>
    </div>
  );
}
