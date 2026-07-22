import { Outlet, useLocation } from 'react-router-dom';
import { MedicoTabBar } from './MedicoTabBar';

/** The tab bar shows on the three top-level médico screens; drill-downs
 * (a cita workspace, a patient ficha) hide it for a focused full-screen. */
const TOP_LEVEL = ['/medico', '/medico/liquidaciones', '/medico/perfil'];

export function MedicoShell() {
  const { pathname } = useLocation();
  const showTabs = TOP_LEVEL.includes(pathname);
  return (
    <div className="relative h-full">
      <Outlet />
      {showTabs && <MedicoTabBar />}
    </div>
  );
}
