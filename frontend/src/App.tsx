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
import { Asistente } from './routes/patient/Asistente';
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
import { Inicio as EmpresaInicio } from './routes/empresa/Inicio';
import { Servicios as EmpresaServicios } from './routes/empresa/Servicios';
import { Promociones as EmpresaPromociones } from './routes/empresa/Promociones';
import { Agendas as EmpresaAgendas } from './routes/empresa/Agendas';
import { Info as EmpresaInfo } from './routes/empresa/Info';
import { Funcionarios as EmpresaFuncionarios } from './routes/empresa/Funcionarios';
import { Crm as EmpresaCrm } from './routes/empresa/Crm';
import { Inicio as AdminInicio } from './routes/admin/Inicio';
import { Clinicas as AdminClinicas } from './routes/admin/Clinicas';
import { Usuarios as AdminUsuarios } from './routes/admin/Usuarios';
import { Config as AdminConfig } from './routes/admin/Config';
import { Finanzas as AdminFinanzas } from './routes/admin/Finanzas';
import { Auditoria as AdminAuditoria } from './routes/admin/Auditoria';
import { Integraciones as AdminIntegraciones } from './routes/admin/Integraciones';
import { Consolidado as AdminCrmConsolidado } from './routes/admin/crm/Consolidado';
import { DetalleClinica as AdminCrmDetalle } from './routes/admin/crm/DetalleClinica';
import { Liquidaciones as AdminCrmLiquidaciones } from './routes/admin/crm/Liquidaciones';
import { CampanasClinica as AdminCrmCampanas } from './routes/admin/crm/CampanasClinica';
import { CampanasEmpresa } from './routes/empresa/CampanasEmpresa';
import { Inicio as AsegInicio } from './routes/aseguradora/Inicio';
import { Convenios as AsegConvenios } from './routes/aseguradora/Convenios';
import { Autorizaciones as AsegAutorizaciones } from './routes/aseguradora/Autorizaciones';
import { Liquidaciones as AsegLiquidaciones } from './routes/aseguradora/Liquidaciones';
import { Padron as AsegPadron } from './routes/aseguradora/Padron';
import { Red as AsegRed } from './routes/aseguradora/Red';

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
                {/* Asistente WhatsApp: pantalla completa (sin barra de tabs). */}
                <Route path="/app/asistente" element={<Asistente />} />
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

            {/* ── Empresa / Cliente ── */}
            <Route element={<RequireRole role="empresa" />}>
              <Route path="/empresa" element={<EmpresaInicio />} />
              <Route path="/empresa/agendas" element={<EmpresaAgendas />} />
              <Route path="/empresa/servicios" element={<EmpresaServicios />} />
              <Route path="/empresa/promociones" element={<EmpresaPromociones />} />
              <Route path="/empresa/info" element={<EmpresaInfo />} />
              <Route path="/empresa/funcionarios" element={<EmpresaFuncionarios />} />
              <Route path="/empresa/crm" element={<EmpresaCrm />} />
              <Route path="/empresa/campanas" element={<CampanasEmpresa />} />
            </Route>

            {/* ── Administrador ── */}
            <Route element={<RequireRole role="admin" />}>
              <Route path="/admin" element={<AdminInicio />} />
              <Route path="/admin/clinicas" element={<AdminClinicas />} />
              <Route path="/admin/usuarios" element={<AdminUsuarios />} />
              <Route path="/admin/config" element={<AdminConfig />} />
              <Route path="/admin/finanzas" element={<AdminFinanzas />} />
              <Route path="/admin/auditoria" element={<AdminAuditoria />} />
              <Route path="/admin/integraciones" element={<AdminIntegraciones />} />
              <Route path="/admin/crm" element={<AdminCrmConsolidado />} />
              <Route path="/admin/crm/liquidaciones" element={<AdminCrmLiquidaciones />} />
              <Route path="/admin/crm/:clinicId/campanas" element={<AdminCrmCampanas />} />
              <Route path="/admin/crm/:clinicId" element={<AdminCrmDetalle />} />
            </Route>

            {/* ── Aseguradora / Prestador ── */}
            <Route element={<RequireRole role="aseguradora" />}>
              <Route path="/aseguradora" element={<AsegInicio />} />
              <Route path="/aseguradora/convenios" element={<AsegConvenios />} />
              <Route path="/aseguradora/autorizaciones" element={<AsegAutorizaciones />} />
              <Route path="/aseguradora/liquidaciones" element={<AsegLiquidaciones />} />
              <Route path="/aseguradora/afiliados" element={<AsegPadron />} />
              <Route path="/aseguradora/red" element={<AsegRed />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppFrame>
    </AuthProvider>
  );
}

export default App;
