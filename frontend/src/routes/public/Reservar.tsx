import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import { money, hhmm } from '../../lib/citas';
import type { ClinicaPublica, ServicioPublico, SlotPublico, ReservaPublicaOut } from '../../api/types';

const diaLabel = (iso: string) =>
  new Date(iso).toLocaleDateString('es-CL', { weekday: 'long', day: '2-digit', month: 'short' });

/** Agenda online pública (60): reserva sin login en /reservar/:slug. */
export function Reservar() {
  const { slug = '' } = useParams();
  const [clinica, setClinica] = useState<ClinicaPublica | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [servicio, setServicio] = useState<ServicioPublico | null>(null);
  const [slots, setSlots] = useState<SlotPublico[]>([]);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [slot, setSlot] = useState<SlotPublico | null>(null);

  const [nombre, setNombre] = useState('');
  const [rut, setRut] = useState('');
  const [telefono, setTelefono] = useState('');
  const [email, setEmail] = useState('');
  const [notas, setNotas] = useState('');
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState<ReservaPublicaOut | null>(null);

  useEffect(() => {
    api.publica.clinica(slug)
      .then(setClinica)
      .catch(() => setError('No encontramos esta clínica.'))
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    if (!servicio) { setSlots([]); return; }
    setLoadingSlots(true); setSlot(null);
    api.publica.disponibilidad(slug, servicio.id)
      .then(setSlots)
      .catch(() => setSlots([]))
      .finally(() => setLoadingSlots(false));
  }, [slug, servicio]);

  // Agrupa los slots por día para una grilla legible.
  const porDia = useMemo(() => {
    const g: Record<string, SlotPublico[]> = {};
    for (const s of slots) {
      const k = s.inicio.slice(0, 10);
      (g[k] ||= []).push(s);
    }
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [slots]);

  const reservar = async () => {
    if (!servicio || !slot) return;
    setSaving(true); setError(null);
    try {
      const res = await api.publica.reservar(slug, {
        service_id: servicio.id, professional_id: slot.professional_id,
        inicio: slot.inicio, fin: slot.fin,
        nombre: nombre.trim(), rut: rut.trim() || undefined,
        telefono: telefono.trim() || undefined, email: email.trim() || undefined,
        notas: notas.trim() || undefined,
      });
      setOk(res);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo enviar la solicitud.');
    } finally { setSaving(false); }
  };

  if (loading) return <Centered><Spinner /></Centered>;
  if (error && !clinica) return <Centered><div className="text-sm text-sub">{error}</div></Centered>;
  if (!clinica) return null;

  if (!clinica.habilitada) {
    return (
      <Centered>
        <div className="text-center">
          <div className="font-heading font-extrabold text-[20px] text-ink">{clinica.nombre}</div>
          <div className="mt-2 text-sm text-sub">La reserva en línea no está disponible por ahora.</div>
        </div>
      </Centered>
    );
  }

  if (ok) {
    return (
      <Centered>
        <div className="w-full text-center flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-full bg-[#E6F7F0] grid place-items-center text-teal text-2xl">✓</div>
          <div className="font-heading font-extrabold text-[20px] text-ink">¡Solicitud enviada!</div>
          <div className="text-sm text-sub leading-relaxed">
            {clinica.nombre} confirmará tu hora a la brevedad.
            {ok.profesional_nombre && <> Profesional: <b className="text-ink">{ok.profesional_nombre}</b>.</>}
          </div>
          <div className="w-full rounded-2xl border border-border bg-white px-4 py-3 text-left">
            <div className="text-[11px] text-sub">Servicio</div>
            <div className="font-semibold text-ink">{ok.servicio_nombre}</div>
            <div className="mt-2 text-[11px] text-sub">Fecha y hora</div>
            <div className="font-semibold text-ink capitalize">{diaLabel(ok.inicio)} · {hhmm(ok.inicio)}</div>
            <div className="mt-2 text-[11px] text-sub">Código de tu solicitud</div>
            <div className="font-mono font-bold text-teal tracking-wider">{ok.codigo}</div>
          </div>
          <div className="text-[11px] text-sub">Guarda este código para consultar el estado de tu hora.</div>
        </div>
      </Centered>
    );
  }

  return (
    <div className="h-full overflow-y-auto scrollhide px-6 py-8 flex flex-col gap-5">
      <div>
        <div className="font-heading font-extrabold text-[22px] text-teal">{clinica.nombre}</div>
        <div className="mt-1 text-sm text-sub leading-relaxed">{clinica.mensaje || 'Reserva tu hora en línea.'}</div>
      </div>

      {/* 1 · Servicio */}
      <Section n={1} titulo="Elige el servicio">
        <div className="flex flex-col gap-2">
          {clinica.servicios.map((s) => (
            <button key={s.id} onClick={() => setServicio(s)}
              className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${servicio?.id === s.id ? 'border-teal bg-[#F0FBF7]' : 'border-border bg-white'}`}>
              <div>
                <div className="font-semibold text-[14px] text-ink">{s.icono ? `${s.icono} ` : ''}{s.nombre}</div>
                <div className="text-[11px] text-sub">{s.especialidad || 'General'} · {s.duracion_min} min</div>
              </div>
              <div className="font-semibold text-ink tabular-nums">{money(s.precio)}</div>
            </button>
          ))}
          {clinica.servicios.length === 0 && <div className="text-sm text-sub">No hay servicios disponibles.</div>}
        </div>
      </Section>

      {/* 2 · Horario */}
      {servicio && (
        <Section n={2} titulo="Elige el horario">
          {loadingSlots ? <Spinner /> : porDia.length === 0 ? (
            <div className="text-sm text-sub">Sin horas disponibles próximamente.</div>
          ) : (
            <div className="flex flex-col gap-3">
              {porDia.map(([dia, ss]) => (
                <div key={dia}>
                  <div className="text-[12px] font-semibold text-ink capitalize mb-1.5">{diaLabel(ss[0].inicio)}</div>
                  <div className="flex flex-wrap gap-2">
                    {ss.map((s, i) => {
                      const active = slot?.inicio === s.inicio && slot?.professional_id === s.professional_id;
                      return (
                        <button key={`${s.professional_id}-${s.inicio}-${i}`} onClick={() => setSlot(s)}
                          className={`rounded-xl border px-3 py-2 text-[12.5px] transition ${active ? 'border-teal bg-teal text-white' : 'border-border bg-white text-ink'}`}
                          title={s.profesional_nombre}>
                          {hhmm(s.inicio)}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
          {slot && <div className="mt-2 text-[12px] text-sub">Con {slot.profesional_nombre || 'el profesional disponible'}.</div>}
        </Section>
      )}

      {/* 3 · Datos de contacto */}
      {servicio && slot && (
        <Section n={3} titulo="Tus datos">
          <div className="flex flex-col gap-2">
            <Input value={nombre} onChange={setNombre} placeholder="Nombre y apellido" />
            <Input value={rut} onChange={setRut} placeholder="RUT (opcional)" />
            <Input value={telefono} onChange={setTelefono} placeholder="Teléfono (opcional)" />
            <Input value={email} onChange={setEmail} placeholder="Email (opcional)" />
            <Input value={notas} onChange={setNotas} placeholder="Motivo o comentario (opcional)" />
          </div>
          {error && <div className="mt-2 text-xs text-danger">{error}</div>}
          <Button onClick={reservar} disabled={saving || nombre.trim().length < 2} className="w-full mt-3">
            {saving ? 'Enviando…' : 'Solicitar hora'}
          </Button>
        </Section>
      )}
    </div>
  );
}

function Section({ n, titulo, children }: { n: number; titulo: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-6 h-6 rounded-full bg-teal text-white grid place-items-center text-[12px] font-bold">{n}</div>
        <div className="font-heading font-bold text-[14px] text-ink">{titulo}</div>
      </div>
      {children}
    </div>
  );
}

function Input({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder: string }) {
  return (
    <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder}
      className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
  );
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="h-full flex items-center justify-center px-8">{children}</div>;
}

function Spinner() {
  return <div className="w-8 h-8 rounded-full border-2 border-[#CDEEE1] border-t-teal animate-spin mx-auto" />;
}
