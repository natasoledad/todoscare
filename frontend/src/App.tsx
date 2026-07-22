import { Navigate, Route, Routes } from 'react-router-dom';
import { AppFrame } from './components/AppFrame';
import { AuthProvider } from './context/AuthContext';
import { Landing } from './routes/Landing';
import { Login } from './routes/Login';
import { Register } from './routes/Register';
import { Onboarding } from './routes/Onboarding';
import { QrResolve } from './routes/QrResolve';
import { RequireAuth, RequireOnboarded, RequireRole } from './routes/ProtectedRoute';
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
import { MedicoShell } from './routes/medico/MedicoShell';
import { Agenda as MedicoAgenda } from './routes/medico/Agenda';
import { Cita as MedicoCita } from './routes/medico/Cita';
import { Ficha as MedicoFicha } from './routes/medico/Ficha';
import { Liquidaciones as MedicoLiquidaciones } from './routes/medico/Liquidaciones';
import { Perfil as MedicoPerfil } from './routes/medico/Perfil';

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
            {/* ── Paciente ── */}
            <Route element={<RequireRole role="paciente" />}>
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

            {/* ── Médico ── */}
            <Route element={<RequireRole role="medico" />}>
              <Route path="/medico" element={<MedicoShell />}>
                <Route index element={<MedicoAgenda />} />
                <Route path="liquidaciones" element={<MedicoLiquidaciones />} />
                <Route path="perfil" element={<MedicoPerfil />} />
                <Route path="cita/:citaId" element={<MedicoCita />} />
                <Route path="ficha/:patientId" element={<MedicoFicha />} />
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
