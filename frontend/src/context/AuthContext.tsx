import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, clearToken, getToken, setToken } from '../api/client';
import type { PatientMe, RegisterInput } from '../api/types';

interface AuthContextValue {
  patient: PatientMe | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (correo: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => void;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [patient, setPatient] = useState<PatientMe | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    const me = await api.patients.me();
    setPatient(me);
  }, []);

  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          await refreshMe();
        } catch {
          clearToken();
          setPatient(null);
        }
      }
      setLoading(false);
    })();
  }, [refreshMe]);

  const login = useCallback(
    async (correo: string, password: string) => {
      const { access_token } = await api.auth.login(correo, password);
      setToken(access_token);
      await refreshMe();
    },
    [refreshMe],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const { access_token } = await api.patients.register(input);
      setToken(access_token);
      await refreshMe();
    },
    [refreshMe],
  );

  const logout = useCallback(() => {
    clearToken();
    setPatient(null);
  }, []);

  return (
    <AuthContext.Provider value={{ patient, loading, isAuthenticated: !!patient, login, register, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
