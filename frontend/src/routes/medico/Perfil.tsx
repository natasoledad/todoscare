import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { Button } from '../../components/Button';
import { useAuth } from '../../context/AuthContext';

export function Perfil() {
  const navigate = useNavigate();
  const { me, logout } = useAuth();
  if (!me) return null;

  return (
    <div className="h-full overflow-y-auto scrollhide pb-[90px]">
      <ScreenHeader title="Mi perfil" subtitle="Profesional de salud" />

      <div className="mx-5 mt-2.5 rounded-2xl border border-border bg-white p-4 flex items-center gap-3.5">
        <div className="w-14 h-14 rounded-full bg-teal-soft flex items-center justify-center text-2xl">🩺</div>
        <div>
          <div className="font-heading font-extrabold text-lg text-ink">{me.nombre}</div>
          <div className="text-xs text-sub mt-0.5">{me.email}</div>
          <div className="text-[11px] text-teal font-heading font-bold uppercase tracking-wider mt-1">Médico tratante</div>
        </div>
      </div>

      <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Responsabilidad sanitaria</div>
      <div className="mx-5 mt-2.5 rounded-2xl border border-border bg-white p-4 text-[13px] leading-relaxed text-sub">
        Eres responsable del acto clínico, la exactitud del prontuario y las prescripciones. Cada acceso a la ficha de
        un paciente y cada cambio quedan auditados de forma inmutable.
      </div>

      <div className="px-5 pt-6">
        <Button
          onClick={() => {
            logout();
            navigate('/');
          }}
          variant="outline"
          className="w-full"
        >
          Cerrar sesión
        </Button>
      </div>
    </div>
  );
}
