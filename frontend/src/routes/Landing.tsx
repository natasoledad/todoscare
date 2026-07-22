import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';

export function Landing() {
  const navigate = useNavigate();
  return (
    <div className="h-full flex flex-col scrollhide overflow-y-auto">
      <div className="flex-1 flex flex-col justify-center px-8 gap-8 text-center">
        <div>
          <div className="font-heading font-extrabold text-[28px] text-teal">TODOSCARE</div>
          <div className="mt-2 text-sm text-sub leading-relaxed">
            Tu salud, en un solo lugar. Onboarding simple, telemedicina, laboratorio, farmacia y billetera con
            cashback.
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <Button onClick={() => navigate('/login')} className="w-full">
            Iniciar sesión
          </Button>
          <Button onClick={() => navigate('/register')} variant="outline" className="w-full">
            Crear cuenta nueva
          </Button>
        </div>
      </div>
    </div>
  );
}
