import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useAuth } from '../context/AuthContext';
import { ApiError } from '../api/client';

export function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [correo, setCorreo] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const role = await login(correo, password);
      navigate(role === 'medico' ? '/medico' : '/app');
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo iniciar sesión');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-8">
        <div className="font-heading font-extrabold text-2xl text-teal">TODOSCARE</div>
        <div className="mt-3.5 font-heading font-extrabold text-xl text-ink">Inicia sesión</div>
      </div>
      <div className="flex-1 px-[22px] pt-6 flex flex-col gap-3">
        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">Correo electrónico</div>
          <input
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
            placeholder="tu@correo.com"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
          />
        </div>
        <div>
          <div className="mb-1.5 font-heading font-semibold text-xs text-sub">Contraseña</div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm font-medium text-ink outline-none focus:border-teal"
          />
        </div>
        {error && <div className="text-xs text-danger">{error}</div>}
      </div>
      <div className="px-5 pb-6 flex flex-col gap-2.5">
        <Button onClick={submit} disabled={submitting || !correo || !password} className="w-full">
          {submitting ? 'Entrando…' : 'Entrar'}
        </Button>
        <Button onClick={() => navigate('/register')} variant="ghost" className="w-full">
          Crear cuenta nueva
        </Button>
      </div>
    </div>
  );
}
