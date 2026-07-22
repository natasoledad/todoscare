import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, clearToken, getToken, setToken } from '../api/client';
import type { Me, PatientMe, RegisterInput } from '../api/types';

type PrimaryRole = 'paciente' | 'medico' | 'empresa' | 'admin' | 'aseguradora' | 'otro';

function pickPrimaryRole(roles: string[]): PrimaryRole {
  // If a user somehow has several roles, route to the most privileged
  // clinical workspace first. Patients are the default landing.
  const order: PrimaryRole[] = ['admin', 'medico', 'empresa', 'aseguradora', 'paciente'];
  for (const r of order) {
    if (roles.includes(r) || (r === 'admin' && (roles.includes('super_admin') || roles.includes('clinic_admin') || roles.includes('branch_admin')))) {
      return r;
    }
  }
  return 'otro';
}

interface AuthContextValue {
  me: Me | null;
  patient: PatientMe | null;
  primaryRole: PrimaryRole | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (correo: string, password: string) => Promise<PrimaryRole>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [patient, setPatient] = useState<PatientMe | null>(null);
  const [loading, setLoading] = useState(true);

  const loadSession = useCallback(async () => {
    const meData = await api.auth.me();
    setMe(meData);
    if (meData.roles.includes('paciente')) {
      setPatient(await api.patients.me());
    } else {
      setPatient(null);
    }
    return meData;
  }, []);

  const refreshMe = useCallback(async () => {
    const meData = await api.auth.me();
    setMe(meData);
    if (meData.roles.includes('paciente')) setPatient(await api.patients.me());
  }, []);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          await loadSession();
        } catch {
          clearToken();
          setMe(null);
          setPatient(null);
        }
      }
      setLoading(false);
    })();
  }, [loadSession]);

  const login = useCallback(
    async (correo: string, password: string) => {
      const { access_token } = await api.auth.login(correo, password);
      setToken(access_token);
      const meData = await loadSession();
      return pickPrimaryRole(meData.roles);
    },
    [loadSession],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const { access_token } = await api.patients.register(input);
      setToken(access_token);
      await loadSession();
    },
    [loadSession],
  );

  const logout = useCallback(() => {
    clearToken();
    setMe(null);
    setPatient(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        me,
        patient,
        primaryRole: me ? pickPrimaryRole(me.roles) : null,
        loading,
        isAuthenticated: !!me,
        login,
        register,
        logout,
        refreshMe,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
