import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';
import type { FichaUpdateInput } from '../../api/types';

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

  if (!patient) return null;

  const complete = FIELDS.every((f) => !!(values[f.key] as string | undefined)?.trim());

  const save = async () => {
    setSaving(true);
    await api.patients.updateFicha(values);
    await refreshMe();
    setSaving(false);
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Ficha clínica" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        {!complete && (
          <div className="rounded-2xl bg-warn-bg border border-warn-border p-3.5 text-xs leading-relaxed text-[#8A6A00]">
            ✨ Completa tu ficha al 100% y gana +300 pts para subir a Oro.
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
        <Button onClick={save} disabled={saving} className="w-full mt-2">
          {saving ? 'Guardando…' : 'Guardar ficha'}
        </Button>
      </div>
    </div>
  );
}
