import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Loading = () => <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;

export function RequireAuth() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <Loading />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

const HOME_BY_ROLE: Record<string, string> = { medico: '/medico', empresa: '/empresa' };

/** Gate a subtree to a single role; bounce others to their own home. */
export function RequireRole({ role }: { role: 'paciente' | 'medico' | 'empresa' }) {
  const { primaryRole, loading } = useAuth();
  if (loading) return <Loading />;
  if (primaryRole !== role) return <Navigate to={HOME_BY_ROLE[primaryRole ?? ''] ?? '/app'} replace />;
  return <Outlet />;
}

export function RequireOnboarded() {
  const { patient, loading } = useAuth();
  if (loading) return <Loading />;
  if (patient && !patient.onboarding_completado) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
