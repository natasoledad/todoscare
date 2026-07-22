import { NavLink } from 'react-router-dom';

const TABS = [
  { to: '/app', label: 'Inicio', icon: '🏠', end: true },
  { to: '/app/agenda', label: 'Agenda', icon: '📅', end: false },
  { to: '/app/salud', label: 'Salud', icon: '📋', end: false },
  { to: '/app/farmacia', label: 'Farmacia', icon: '💊', end: false },
  { to: '/app/perfil', label: 'Perfil', icon: '👤', end: false },
];

export function TabBar() {
  return (
    <div className="absolute left-0 right-0 bottom-0 h-[78px] bg-white/92 backdrop-blur-md border-t border-[#ECF1EF] flex pb-[18px]">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-end gap-[3px] pt-2.5 cursor-pointer ${
              isActive ? 'text-teal' : 'text-[#A6B4B0]'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <div className={`text-xl ${isActive ? '' : 'grayscale opacity-70'}`}>{tab.icon}</div>
              <div className={`text-[10.5px] font-heading ${isActive ? 'font-bold' : 'font-medium'}`}>{tab.label}</div>
            </>
          )}
        </NavLink>
      ))}
    </div>
  );
}
