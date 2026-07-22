import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { BackHeader } from '../../components/BackHeader';
import { ListRow, Chevron } from '../../components/ListRow';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import type { Cita, Servicio, Slot } from '../../api/types';

type Step = 'list' | 'slots' | 'confirm';

function formatSlot(iso: string) {
  return new Date(iso).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' });
}

export function Agenda() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>('list');
  const [servicios, setServicios] = useState<Servicio[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedServicio, setSelectedServicio] = useState<Servicio | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [cita, setCita] = useState<Cita | null>(null);
  const [booking, setBooking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.agenda.servicios().then(setServicios);
  }, []);

  const loadSlots = async (servicio: Servicio) => {
    setSelectedServicio(servicio);
    setStep('slots');
    setError(null);
    setSlots(await api.agenda.disponibilidad(servicio.id));
  };

  const pickSlot = async (slot: Slot) => {
    if (!selectedServicio) return;
    setSelectedSlot(slot);
    setBooking(true);
    setError(null);
    try {
      const nuevaCita = await api.agenda.reservar({
        service_id: selectedServicio.id,
        professional_id: slot.professional_id,
        inicio: slot.inicio,
        fin: slot.fin,
      });
      setCita(nuevaCita);
      setStep('confirm');
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError('Ese horario ya no está disponible — elige otro.');
        setSlots(await api.agenda.disponibilidad(selectedServicio.id));
        setSelectedSlot(null);
      } else {
        setError('No se pudo agendar. Intenta nuevamente.');
      }
    } finally {
      setBooking(false);
    }
  };

  const back = () => {
    if (step === 'slots') {
      setStep('list');
      setSelectedServicio(null);
    }
  };

  const reset = () => {
    setStep('list');
    setSelectedServicio(null);
    setSelectedSlot(null);
    setCita(null);
  };

  if (step === 'list') {
    return (
      <div className="h-full flex flex-col">
        <ScreenHeader title="Agenda" subtitle="Elige una especialidad para ver disponibilidad" />
        <div className="flex-1 overflow-y-auto scrollhide px-5 pt-2.5 pb-[90px] flex flex-col gap-2.5">
          {servicios.map((sp) => (
            <ListRow
              key={sp.id}
              icon={sp.icono}
              title={sp.nombre}
              subtitle={`${sp.duracion_min} min · $${sp.precio}`}
              trailing={<Chevron />}
              onClick={() => loadSlots(sp)}
            />
          ))}
        </div>
      </div>
    );
  }

  if (step === 'slots' && selectedServicio) {
    return (
      <div className="h-full flex flex-col">
        <BackHeader title={selectedServicio.nombre} onBack={back} />
        <div className="px-6 pt-1.5 text-[13px] text-sub">Horarios disponibles hoy · cerca de tu ubicación</div>
        {error && <div className="mx-6 mt-2 text-xs text-danger">{error}</div>}
        <div className="px-5 pt-[18px] grid grid-cols-2 gap-2.5 overflow-y-auto scrollhide pb-[90px]">
          {slots.length === 0 && <div className="col-span-2 text-center text-sm text-sub py-6">No hay horarios disponibles.</div>}
          {slots.map((slot) => (
            <div
              key={slot.inicio + slot.professional_id}
              onClick={() => !booking && pickSlot(slot)}
              className="text-center rounded-2xl border-[1.5px] border-border-strong bg-white px-3.5 py-3.5 font-heading font-bold text-[15px] text-ink cursor-pointer"
            >
              {booking && selectedSlot?.inicio === slot.inicio ? '…' : formatSlot(slot.inicio)}
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col items-center justify-center px-7 text-center animate-fade-up">
      <div className="w-[78px] h-[78px] rounded-full bg-teal-soft flex items-center justify-center text-4xl">✅</div>
      <div className="mt-4 font-heading font-extrabold text-xl text-ink">Cita confirmada</div>
      <div className="mt-1.5 text-sm leading-relaxed text-sub">
        {cita?.servicio_nombre} · {cita && new Date(cita.inicio).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })}
      </div>
      <div className="mt-1 text-xs text-sub">{cita?.ubicacion}</div>
      <div className="mt-[18px] w-full flex flex-col gap-2.5">
        <Button onClick={reset} className="w-full">
          Agendar otra cita
        </Button>
        <Button onClick={() => navigate('/app')} variant="ghost" className="w-full">
          Volver al inicio
        </Button>
      </div>
    </div>
  );
}
