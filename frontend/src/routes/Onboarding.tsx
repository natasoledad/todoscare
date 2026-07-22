import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { Dots } from '../components/Dots';
import { SuccessScreen, LevelBadge } from '../components/SuccessScreen';
import { api } from '../api/client';
import { useAuth } from '../context/AuthContext';
import type { OnboardingAnswers } from '../api/types';

interface Question {
  key: keyof OnboardingAnswers;
  q: string;
  opts: string[];
}

const QUESTIONS: Question[] = [
  {
    key: 'motivo',
    q: '¿Cuál es tu principal motivo para unirte a TODOSCARE?',
    opts: ['Prevención y chequeos', 'Seguimiento de una enfermedad o preexistencia', 'Bienestar y nutrición', 'Salud mental'],
  },
  {
    key: 'condicion',
    q: '¿Tienes alguna condición médica diagnosticada?',
    opts: ['Ninguna', 'Hipertensión', 'Diabetes', 'Prefiero decirlo con mi médico'],
  },
  {
    key: 'actividad',
    q: '¿Con qué frecuencia haces actividad física?',
    opts: ['Casi nunca', '1-2 veces/semana', '3-4 veces/semana', 'Todos los días'],
  },
  {
    key: 'alergias',
    q: '¿Tienes alergias a medicamentos?',
    opts: ['No', 'Sí, penicilina', 'Sí, otra', 'No estoy seguro'],
  },
  {
    key: 'seguro',
    q: '¿Cuentas con seguro médico o Isapre?',
    opts: ['Sí', 'No', 'En trámite'],
  },
];

const EMPTY_ANSWERS: OnboardingAnswers = { motivo: null, condicion: null, actividad: null, alergias: null, seguro: null };

export function Onboarding() {
  const navigate = useNavigate();
  const { refreshMe, patient } = useAuth();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<OnboardingAnswers>(EMPTY_ANSWERS);
  const [dependents, setDependents] = useState<{ nombre: string }[]>([]);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [newLevel, setNewLevel] = useState('Plata');

  const answerQ = (key: keyof OnboardingAnswers, val: string) => setAnswers((a) => ({ ...a, [key]: val }));
  const next = () => setStep((s) => Math.min(s + 1, QUESTIONS.length));
  const prev = () => setStep((s) => Math.max(s - 1, 0));

  const addDependent = () => setDependents((d) => [...d, { nombre: `Dependiente ${d.length + 1}` }]);
  const removeDependent = (i: number) => setDependents((d) => d.filter((_, idx) => idx !== i));

  const finish = async () => {
    setSubmitting(true);
    const updated = await api.patients.onboarding({ answers, dependents });
    setNewLevel(updated.nivel);
    await refreshMe();
    setSubmitting(false);
    setDone(true);
  };

  if (done) {
    return (
      <SuccessScreen
        emoji="✅"
        title="¡Todo listo!"
        description="Tu perfil básico está activo. Completa tu ficha clínica cuando quieras y sube de nivel en la plataforma."
        badge={<LevelBadge emoji="🥈" label={`Nivel ${newLevel} desbloqueado`} />}
      >
        <div className="mt-3.5 flex flex-col gap-2.5 w-full max-w-[220px]">
          <Button onClick={() => navigate('/app')} className="w-full">
            Ir a la app
          </Button>
        </div>
      </SuccessScreen>
    );
  }

  if (patient?.onboarding_completado) {
    navigate('/app', { replace: true });
    return null;
  }

  const totalSteps = QUESTIONS.length + 1;

  if (step < QUESTIONS.length) {
    const question = QUESTIONS[step];
    const answered = answers[question.key];
    return (
      <div className="h-full flex flex-col">
        <div className="flex items-center gap-3 px-[22px] pt-[18px]">
          {step > 0 ? (
            <div onClick={prev} className="cursor-pointer text-lg text-sub">
              ←
            </div>
          ) : (
            <div className="w-[18px]" />
          )}
          <div className="flex-1">
            <Dots count={totalSteps} active={step} />
          </div>
          <div className="w-[15px]" />
        </div>
        <div className="px-6 pt-7 font-heading font-bold text-[11px] tracking-[0.1em] uppercase text-teal">
          Pregunta {step + 1} de {QUESTIONS.length}
        </div>
        <div className="px-6 pt-2 font-heading font-extrabold text-[21px] leading-snug text-ink">{question.q}</div>
        <div className="px-5 pt-[22px] flex flex-col gap-2.5 flex-1 overflow-y-auto scrollhide">
          {question.opts.map((opt) => (
            <div
              key={opt}
              onClick={() => answerQ(question.key, opt)}
              className={`flex items-center justify-between rounded-2xl px-4 py-[15px] cursor-pointer text-[14.5px] font-semibold ${
                answered === opt
                  ? 'border-2 border-teal bg-teal-soft text-teal-dark'
                  : 'border-[1.5px] border-border-strong bg-white text-ink'
              }`}
            >
              {opt}
              {answered === opt && <span className="text-teal">✓</span>}
            </div>
          ))}
        </div>
        <div className="px-5 pb-[22px]">
          <Button onClick={next} disabled={!answered} className="w-full">
            {step === QUESTIONS.length - 1 ? 'Continuar a dependientes' : 'Siguiente'}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-3 px-[22px] pt-[18px]">
        <div onClick={prev} className="cursor-pointer text-lg text-sub">
          ←
        </div>
        <div className="flex-1">
          <Dots count={totalSteps} active={QUESTIONS.length} />
        </div>
        <div className="w-[15px]" />
      </div>
      <div className="px-6 pt-7 font-heading font-extrabold text-[21px] text-ink">¿Deseas agregar dependientes?</div>
      <div className="px-6 pt-2 text-[13.5px] leading-relaxed text-sub">
        Hijos menores de 18 años pueden vincularse a tu cuenta para acceder a su información de salud.
      </div>
      <div className="px-5 pt-[18px] flex flex-col gap-2.5 flex-1 overflow-y-auto scrollhide">
        {dependents.map((d, i) => (
          <div key={i} className="flex items-center gap-3 rounded-2xl border-[1.5px] border-border-strong bg-white px-3.5 py-3.5">
            <div className="w-[38px] h-[38px] rounded-full bg-teal-soft flex items-center justify-center text-lg">🧒</div>
            <div className="flex-1 font-semibold text-sm text-ink">{d.nombre}</div>
            <div onClick={() => removeDependent(i)} className="cursor-pointer text-[13px] font-bold text-danger">
              Quitar
            </div>
          </div>
        ))}
        <div
          onClick={addDependent}
          className="flex items-center justify-center gap-2.5 rounded-2xl border-[1.5px] border-dashed border-[#B9D4CE] py-3.5 text-teal-dark font-heading font-bold text-sm cursor-pointer"
        >
          + Agregar dependiente
        </div>
      </div>
      <div className="px-5 pb-[22px] flex flex-col gap-2.5">
        <Button onClick={finish} disabled={submitting} className="w-full">
          {submitting ? 'Guardando…' : 'Finalizar registro'}
        </Button>
        <Button onClick={finish} disabled={submitting} variant="ghost" className="w-full">
          Omitir por ahora
        </Button>
      </div>
    </div>
  );
}
