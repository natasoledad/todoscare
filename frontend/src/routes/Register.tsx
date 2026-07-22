import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { BottomSheet } from '../components/BottomSheet';
import { api, ApiError } from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { ClinicPublic, TycVersion } from '../api/types';

interface Fields {
  nombre: string;
  rut: string;
  telefono: string;
  direccion: string;
  correo: string;
  password: string;
}

const EMPTY: Fields = { nombre: '', rut: '', telefono: '', direccion: '', correo: '', password: '' };

const FIELD_DEFS: { key: keyof Fields; label: string; placeholder: string; type?: string }[] = [
  { key: 'nombre', label: 'Nombre completo', placeholder: 'Camila Rodríguez' },
  { key: 'rut', label: 'RUT / ID', placeholder: '18.245.301-K' },
  { key: 'telefono', label: 'Teléfono', placeholder: '+52 55 1234 5678' },
  { key: 'direccion', label: 'Dirección', placeholder: 'Av. Providencia 1234' },
  { key: 'correo', label: 'Correo electrónico', placeholder: 'camila@correo.com' },
  { key: 'password', label: 'Crea una contraseña', placeholder: 'Mínimo 8 caracteres', type: 'password' },
];

export function Register() {
  const navigate = useNavigate();
  const { register } = useAuth();
  const [fields, setFields] = useState<Fields>(EMPTY);
  const [tycAccepted, setTycAccepted] = useState(false);
  const [tycOpen, setTycOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clinic, setClinic] = useState<ClinicPublic | null>(null);
  const [tyc, setTyc] = useState<TycVersion | null>(null);

  useEffect(() => {
    (async () => {
      const clinics = await api.clinics.public();
      const chosen = clinics[0];
      setClinic(chosen);
      if (chosen) setTyc(await api.tyc.latest(chosen.pais));
    })();
  }, []);

  const setField = (key: keyof Fields, value: string) => setFields((f) => ({ ...f, [key]: value }));
  const canSubmit = tycAccepted && !submitting && clinic && tyc && Object.values(fields).every((v) => v.length > 0);

  const submit = async () => {
    if (!canSubmit || !clinic || !tyc) return;
    setSubmitting(true);
    setError(null);
    try {
      await register({ ...fields, clinic_id: clinic.id, tyc_version_id: tyc.id });
      navigate('/onboarding');
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la cuenta');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full flex flex-col relative">
      <div className="px-6 pt-6">
        <div className="font-heading font-extrabold text-2xl text-teal">TODOSCARE</div>
        <div className="mt-3.5 font-heading font-extrabold text-xl text-ink">Crea tu cuenta</div>
        <div className="mt-1 text-[13px] text-sub">Solo 5 datos. Rápido y simple.</div>
      </div>

      <div className="flex-1 overflow-y-auto scrollhide px-[22px] pt-4 flex flex-col gap-3">
        {FIELD_DEFS.map((f) => (
          <div key={f.key}>
            <div className="mb-1.5 font-heading font-semibold text-xs text-sub">{f.label}</div>
            <input
              type={f.type}
              value={fields[f.key]}
              placeholder={f.placeholder}
              onChange={(e) => setField(f.key, e.target.value)}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
            />
          </div>
        ))}
        <div
          onClick={() => (tycAccepted ? setTycAccepted(false) : setTycOpen(true))}
          className="flex gap-2.5 items-start cursor-pointer py-2 px-0.5"
        >
          <div
            className={`w-5 h-5 rounded-md shrink-0 flex items-center justify-center text-[13px] text-white ${
              tycAccepted ? 'bg-teal' : 'border-[1.5px] border-[#C6D2CE] bg-white'
            }`}
          >
            {tycAccepted ? '✓' : ''}
          </div>
          <div className="text-xs leading-relaxed text-sub">
            Acepto los <span className="text-teal font-bold underline">términos y condiciones</span> (obligatorio, se
            re-acepta con cada actualización).
          </div>
        </div>
        {error && <div className="text-xs text-danger">{error}</div>}
      </div>

      <div className="px-5 pt-2.5 pb-6">
        <Button onClick={submit} disabled={!canSubmit} className="w-full">
          {submitting ? 'Creando cuenta…' : 'Crear cuenta'}
        </Button>
      </div>

      {tycOpen && tyc && (
        <BottomSheet onClose={() => setTycOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Términos y condiciones</div>
          <div className="text-[12.5px] leading-relaxed text-sub overflow-y-auto">{tyc.contenido}</div>
          <Button onClick={() => { setTycAccepted(true); setTycOpen(false); }} className="w-full">
            Acepto los términos
          </Button>
          <Button onClick={() => setTycOpen(false)} variant="ghost" className="w-full">
            Cerrar
          </Button>
        </BottomSheet>
      )}
    </div>
  );
}
