import { lazy, Suspense, type ComponentType } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { AppFrame } from './components/AppFrame';
import { AuthProvider } from './context/AuthContext';
import { RequireAuth, RequireOnboarded, RequireRole } from './routes/ProtectedRoute';
// Rutas públicas / de entrada: se cargan de inmediato (son la primera pantalla).
import { Landing } from './routes/Landing';
import { Login } from './routes/Login';
import { Register } from './routes/Register';
import { QrResolve } from './routes/QrResolve';

/** Carga diferida de un export con nombre: cada rol baja en su propio chunk,
 *  no en el paquete inicial. Mejora la primera carga en conexiones lentas. */
function lazyNamed<M extends Record<string, unknown>, K extends keyof M>(
  factory: () => Promise<M>,
  name: K,
) {
  return lazy(async () => ({ default: (await factory())[name] as ComponentType }));
}

// ── Paciente ──
const Onboarding = lazyNamed(() => import('./routes/Onboarding'), 'Onboarding');
const AppShell = lazyNamed(() => import('./routes/patient/AppShell'), 'AppShell');
const Home = lazyNamed(() => import('./routes/patient/Home'), 'Home');
const Agenda = lazyNamed(() => import('./routes/patient/Agenda'), 'Agenda');
const Farmacia = lazyNamed(() => import('./routes/patient/Farmacia'), 'Farmacia');
const Perfil = lazyNamed(() => import('./routes/patient/Perfil'), 'Perfil');
const Wallet = lazyNamed(() => import('./routes/patient/Wallet'), 'Wallet');
const Asistente = lazyNamed(() => import('./routes/patient/Asistente'), 'Asistente');
const SaludMenu = lazyNamed(() => import('./routes/salud/SaludMenu'), 'SaludMenu');
const Ficha = lazyNamed(() => import('./routes/salud/Ficha'), 'Ficha');
const Examenes = lazyNamed(() => import('./routes/salud/Examenes'), 'Examenes');
const Dental = lazyNamed(() => import('./routes/salud/Dental'), 'Dental');
const Hospitalizaciones = lazyNamed(() => import('./routes/salud/Hospitalizaciones'), 'Hospitalizaciones');
const Agendamientos = lazyNamed(() => import('./routes/salud/Agendamientos'), 'Agendamientos');
const Qr = lazyNamed(() => import('./routes/salud/Qr'), 'Qr');
const Subir = lazyNamed(() => import('./routes/salud/Subir'), 'Subir');

// ── Médico ──
const MedicoShell = lazyNamed(() => import('./routes/medico/MedicoShell'), 'MedicoShell');
const MedicoAgenda = lazyNamed(() => import('./routes/medico/Agenda'), 'Agenda');
const MedicoCita = lazyNamed(() => import('./routes/medico/Cita'), 'Cita');
const MedicoFicha = lazyNamed(() => import('./routes/medico/Ficha'), 'Ficha');
const MedicoLiquidaciones = lazyNamed(() => import('./routes/medico/Liquidaciones'), 'Liquidaciones');
const MedicoPerfil = lazyNamed(() => import('./routes/medico/Perfil'), 'Perfil');

// ── Empresa / Cliente ──
const EmpresaInicio = lazyNamed(() => import('./routes/empresa/Inicio'), 'Inicio');
const EmpresaAgendaClinica = lazyNamed(() => import('./routes/empresa/AgendaClinica'), 'AgendaClinica');
const EmpresaCajas = lazyNamed(() => import('./routes/empresa/Cajas'), 'Cajas');
const EmpresaTributario = lazyNamed(() => import('./routes/empresa/Tributario'), 'Tributario');
const EmpresaPacientes = lazyNamed(() => import('./routes/empresa/Pacientes'), 'Pacientes');
const EmpresaDesempeno = lazyNamed(() => import('./routes/empresa/Desempeno'), 'Desempeno');
const EmpresaCrmGestion = lazyNamed(() => import('./routes/empresa/CrmGestion'), 'CrmGestion');
const EmpresaServicios = lazyNamed(() => import('./routes/empresa/Servicios'), 'Servicios');
const EmpresaEspecialidades = lazyNamed(() => import('./routes/empresa/Especialidades'), 'Especialidades');
const EmpresaHorarioSemanal = lazyNamed(() => import('./routes/empresa/HorarioSemanal'), 'HorarioSemanal');
const EmpresaLiquidaciones = lazyNamed(() => import('./routes/empresa/Liquidaciones'), 'Liquidaciones');
const EmpresaMediosPago = lazyNamed(() => import('./routes/empresa/MediosPago'), 'MediosPago');
const EmpresaEntidadesFinancieras = lazyNamed(() => import('./routes/empresa/EntidadesFinancieras'), 'EntidadesFinancieras');
const EmpresaGastos = lazyNamed(() => import('./routes/empresa/Gastos'), 'Gastos');
const EmpresaAranceles = lazyNamed(() => import('./routes/empresa/Aranceles'), 'Aranceles');
const EmpresaPromociones = lazyNamed(() => import('./routes/empresa/Promociones'), 'Promociones');
const EmpresaAgendas = lazyNamed(() => import('./routes/empresa/Agendas'), 'Agendas');
const EmpresaInfo = lazyNamed(() => import('./routes/empresa/Info'), 'Info');
const EmpresaFuncionarios = lazyNamed(() => import('./routes/empresa/Funcionarios'), 'Funcionarios');
const EmpresaCrm = lazyNamed(() => import('./routes/empresa/Crm'), 'Crm');
const CampanasEmpresa = lazyNamed(() => import('./routes/empresa/CampanasEmpresa'), 'CampanasEmpresa');
const EmpresaAgendaOnline = lazyNamed(() => import('./routes/empresa/AgendaOnline'), 'AgendaOnline');
const EmpresaInventario = lazyNamed(() => import('./routes/empresa/Inventario'), 'Inventario');
const EmpresaLaboratorios = lazyNamed(() => import('./routes/empresa/Laboratorios'), 'Laboratorios');

// ── Pública (sin login) ──
const Reservar = lazyNamed(() => import('./routes/public/Reservar'), 'Reservar');

// ── Administrador ──
const AdminInicio = lazyNamed(() => import('./routes/admin/Inicio'), 'Inicio');
const AdminClinicas = lazyNamed(() => import('./routes/admin/Clinicas'), 'Clinicas');
const AdminUsuarios = lazyNamed(() => import('./routes/admin/Usuarios'), 'Usuarios');
const AdminConfig = lazyNamed(() => import('./routes/admin/Config'), 'Config');
const AdminFinanzas = lazyNamed(() => import('./routes/admin/Finanzas'), 'Finanzas');
const AdminAuditoria = lazyNamed(() => import('./routes/admin/Auditoria'), 'Auditoria');
const AdminIntegraciones = lazyNamed(() => import('./routes/admin/Integraciones'), 'Integraciones');
const AdminCrmConsolidado = lazyNamed(() => import('./routes/admin/crm/Consolidado'), 'Consolidado');
const AdminCrmDetalle = lazyNamed(() => import('./routes/admin/crm/DetalleClinica'), 'DetalleClinica');
const AdminCrmLiquidaciones = lazyNamed(() => import('./routes/admin/crm/Liquidaciones'), 'Liquidaciones');
const AdminCrmCampanas = lazyNamed(() => import('./routes/admin/crm/CampanasClinica'), 'CampanasClinica');

// ── Aseguradora / Prestador ──
const AsegInicio = lazyNamed(() => import('./routes/aseguradora/Inicio'), 'Inicio');
const AsegConvenios = lazyNamed(() => import('./routes/aseguradora/Convenios'), 'Convenios');
const AsegAutorizaciones = lazyNamed(() => import('./routes/aseguradora/Autorizaciones'), 'Autorizaciones');
const AsegLiquidaciones = lazyNamed(() => import('./routes/aseguradora/Liquidaciones'), 'Liquidaciones');
const AsegPadron = lazyNamed(() => import('./routes/aseguradora/Padron'), 'Padron');
const AsegRed = lazyNamed(() => import('./routes/aseguradora/Red'), 'Red');

/** Indicador breve mientras baja el chunk de la sección (redes lentas). */
function RouteFallback() {
  return (
    <div className="flex items-center justify-center py-24">
      <div className="w-8 h-8 rounded-full border-2 border-[#CDEEE1] border-t-teal animate-spin" />
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppFrame>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/qr/:token" element={<QrResolve />} />
            <Route path="/reservar/:slug" element={<Reservar />} />

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
                <Route path="/empresa/agenda-clinica" element={<EmpresaAgendaClinica />} />
                <Route path="/empresa/cajas" element={<EmpresaCajas />} />
                <Route path="/empresa/tributario" element={<EmpresaTributario />} />
                <Route path="/empresa/pacientes" element={<EmpresaPacientes />} />
                <Route path="/empresa/desempeno" element={<EmpresaDesempeno />} />
                <Route path="/empresa/gestion-crm" element={<EmpresaCrmGestion />} />
                <Route path="/empresa/agendas" element={<EmpresaAgendas />} />
                <Route path="/empresa/agenda-online" element={<EmpresaAgendaOnline />} />
                <Route path="/empresa/inventario" element={<EmpresaInventario />} />
                <Route path="/empresa/laboratorios" element={<EmpresaLaboratorios />} />
                <Route path="/empresa/servicios" element={<EmpresaServicios />} />
                <Route path="/empresa/especialidades" element={<EmpresaEspecialidades />} />
                <Route path="/empresa/horario-semanal" element={<EmpresaHorarioSemanal />} />
                <Route path="/empresa/liquidaciones" element={<EmpresaLiquidaciones />} />
                <Route path="/empresa/medios-pago" element={<EmpresaMediosPago />} />
                <Route path="/empresa/entidades-financieras" element={<EmpresaEntidadesFinancieras />} />
                <Route path="/empresa/gastos" element={<EmpresaGastos />} />
                <Route path="/empresa/aranceles" element={<EmpresaAranceles />} />
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
        </Suspense>
      </AppFrame>
    </AuthProvider>
  );
}

export default App;
