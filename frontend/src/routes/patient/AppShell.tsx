import { Outlet } from 'react-router-dom';
import { TabBar } from '../../components/TabBar';

export function AppShell() {
  return (
    <div className="relative h-full">
      <Outlet />
      <TabBar />
    </div>
  );
}
