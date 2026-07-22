import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function RequireAuth() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Outlet />;
}

export function RequireOnboarded() {
  const { patient, loading } = useAuth();
  if (loading) return <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;
  if (patient && !patient.onboarding_completado) return <Navigate to="/onboarding" replace />;
  return <Outlet />;
}
