import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { api, ApiError, getToken, setToken } from '../api/client';

interface Resolved {
  patient_nombre: string;
  resumen: { grupo_sanguineo?: string | null; alergias?: string | null };
}

export function QrResolve() {
  const { token = '' } = useParams();
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [resolved, setResolved] = useState<Resolved | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const tryResolve = async () => {
    setError(null);
    try {
      setResolved(await api.salud.resolverQr(token));
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError('Solo un profesional médico puede escanear este QR.');
      else if (e instanceof ApiError && e.status === 404) setError('QR inválido o inactivo.');
      else setError('No se pudo verificar el QR.');
    }
  };

  const submitLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await api.auth.login(correo, password);
      setToken(access_token);
      await tryResolve();
    } catch {
      setError('Correo o contraseña incorrectos.');
    } finally {
      setLoading(false);
    }
  };

  if (resolved) {
    return (
      <div className="h-full flex flex-col items-center justify-center px-8 text-center gap-3">
        <div className="text-4xl">🆘</div>
        <div className="font-heading font-extrabold text-xl text-ink">{resolved.patient_nombre}</div>
        {resolved.resumen.grupo_sanguineo && <div className="text-sm text-sub">Grupo sanguíneo: {resolved.resumen.grupo_sanguineo}</div>}
        {resolved.resumen.alergias && <div className="text-sm text-sub">Alergias: {resolved.resumen.alergias}</div>}
        <div className="mt-2 text-xs text-sub">Este acceso quedó registrado con tu nombre, fecha y hora.</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col justify-center px-8 gap-4">
      <div className="text-center">
        <div className="font-heading font-extrabold text-xl text-teal">QR de emergencia</div>
        <div className="mt-1 text-sm text-sub">Inicia sesión como profesional médico para ver esta ficha.</div>
      </div>
      {getToken() ? (
        <Button onClick={tryResolve} className="w-full">
          Ver ficha de emergencia
        </Button>
      ) : (
        <>
          <input
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="tu@correo.com"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Contraseña"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
          />
          <Button onClick={submitLogin} disabled={loading || !correo || !password} className="w-full">
            {loading ? 'Verificando…' : 'Entrar y ver ficha'}
          </Button>
        </>
      )}
      {error && <div className="text-center text-xs text-danger">{error}</div>}
    </div>
  );
}
