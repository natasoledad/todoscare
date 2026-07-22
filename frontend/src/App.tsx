import { Navigate, Route, Routes } from 'react-router-dom';
import { AppFrame } from './components/AppFrame';
import { AuthProvider } from './context/AuthContext';
import { Landing } from './routes/Landing';
import { Login } from './routes/Login';
import { Register } from './routes/Register';
import { Onboarding } from './routes/Onboarding';
import { QrResolve } from './routes/QrResolve';
import { RequireAuth, RequireOnboarded } from './routes/ProtectedRoute';
import { AppShell } from './routes/patient/AppShell';
import { Home } from './routes/patient/Home';
import { Agenda } from './routes/patient/Agenda';
import { Farmacia } from './routes/patient/Farmacia';
import { Perfil } from './routes/patient/Perfil';
import { Wallet } from './routes/patient/Wallet';
import { SaludMenu } from './routes/salud/SaludMenu';
import { Ficha } from './routes/salud/Ficha';
import { Examenes } from './routes/salud/Examenes';
import { Dental } from './routes/salud/Dental';
import { Hospitalizaciones } from './routes/salud/Hospitalizaciones';
import { Agendamientos } from './routes/salud/Agendamientos';
import { Qr } from './routes/salud/Qr';
import { Subir } from './routes/salud/Subir';

function App() {
  return (
    <AuthProvider>
      <AppFrame>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/qr/:token" element={<QrResolve />} />

          <Route element={<RequireAuth />}>
            <Route path="/onboarding" element={<Onboarding />} />

            <Route element={<RequireOnboarded />}>
              <Route path="/app" element={<AppShell />}>
                <Route index element={<Home />} />
                <Route path="agenda" element={<Agenda />} />
                <Route path="farmacia" element={<Farmacia />} />
                <Route path="perfil" element={<Perfil />} />
                <Route path="perfil/billetera" element={<Wallet />} />

                <Route path="salud" element={<SaludMenu />} />
                <Route path="salud/ficha" element={<Ficha />} />
                <Route path="salud/examenes" element={<Examenes />} />
                <Route path="salud/dental" element={<Dental />} />
                <Route path="salud/hospitalizaciones" element={<Hospitalizaciones />} />
                <Route path="salud/agendamientos" element={<Agendamientos />} />
                <Route path="salud/qr" element={<Qr />} />
                <Route path="salud/subir" element={<Subir />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppFrame>
    </AuthProvider>
  );
}

export default App;
