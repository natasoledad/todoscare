import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { Button } from '../../components/Button';
import { useAuth } from '../../context/AuthContext';
import { api } from '../../api/client';

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

      <FirmaCard />

      <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Responsabilidad sanitaria</div>
      <div className="mx-5 mt-2.5 rounded-2xl border border-border bg-white p-4 text-[13px] leading-relaxed text-sub">
        Eres responsable del acto clínico, la exactitud del prontuario y las prescripciones. Cada acceso a la ficha de
        un paciente y cada cambio quedan auditados de forma inmutable.
      </div>

      <div className="px-5 pt-6">
        <Button onClick={() => { logout(); navigate('/'); }} variant="outline" className="w-full">Cerrar sesión</Button>
      </div>
    </div>
  );
}

function FirmaCard() {
  const [firma, setFirma] = useState<string | null>(null);
  const [especialidad, setEspecialidad] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.medico.miFirma().then((f) => { setFirma(f.firma); setEspecialidad(f.especialidad); }).catch(() => {});
  }, []);

  const onSaved = (dataUrl: string | null) => {
    setSaving(true);
    api.medico.guardarMiFirma(dataUrl).then((f) => { setFirma(f.firma); setEditing(false); }).finally(() => setSaving(false));
  };

  return (
    <>
      <div className="px-5 pt-5 font-heading font-bold text-[13px] text-ink">Firma del profesional</div>
      <div className="mx-5 mt-2.5 rounded-2xl border border-border bg-white p-4">
        {especialidad && <div className="text-[12px] text-sub mb-2">Especialidad: <span className="text-ink font-semibold">{especialidad}</span></div>}
        {!editing && (
          <>
            {firma ? (
              <div className="rounded-xl border border-border bg-[#FCFCFC] p-2 flex items-center justify-center">
                <img src={firma} alt="Mi firma" className="max-h-24 object-contain" />
              </div>
            ) : (
              <div className="text-[12.5px] text-sub">Aún no has registrado tu firma. Se estampará en los documentos que emitas.</div>
            )}
            <Button onClick={() => setEditing(true)} variant="outline" className="w-full mt-3">
              {firma ? 'Cambiar firma' : 'Dibujar mi firma'}
            </Button>
          </>
        )}
        {editing && <FirmaCanvas saving={saving} onCancel={() => setEditing(false)} onSave={onSaved} />}
      </div>
    </>
  );
}

function FirmaCanvas({ saving, onSave, onCancel }: { saving: boolean; onSave: (d: string | null) => void; onCancel: () => void }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const dirty = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    // Escalado por densidad de pantalla para trazo nítido.
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * ratio;
    canvas.height = rect.height * ratio;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.2;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#0F172A';
  }, []);

  const pos = (e: React.PointerEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  };
  const start = (e: React.PointerEvent) => {
    e.preventDefault();
    drawing.current = true;
    const ctx = canvasRef.current!.getContext('2d')!;
    const { x, y } = pos(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };
  const move = (e: React.PointerEvent) => {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = canvasRef.current!.getContext('2d')!;
    const { x, y } = pos(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    dirty.current = true;
  };
  const end = () => { drawing.current = false; };

  const limpiar = () => {
    const canvas = canvasRef.current!;
    canvas.getContext('2d')!.clearRect(0, 0, canvas.width, canvas.height);
    dirty.current = false;
  };
  const guardar = () => {
    if (!dirty.current) { onSave(null); return; }
    onSave(canvasRef.current!.toDataURL('image/png'));
  };

  return (
    <div className="flex flex-col gap-2.5">
      <div className="text-[11.5px] text-sub">Dibuja tu firma dentro del recuadro con el dedo o el mouse.</div>
      <canvas
        ref={canvasRef}
        onPointerDown={start}
        onPointerMove={move}
        onPointerUp={end}
        onPointerLeave={end}
        className="w-full h-40 rounded-xl border-[1.5px] border-dashed border-border-strong bg-white touch-none"
      />
      <div className="flex gap-2">
        <Button onClick={limpiar} variant="outline" className="flex-1">Limpiar</Button>
        <Button onClick={onCancel} variant="outline" className="flex-1">Cancelar</Button>
        <Button onClick={guardar} disabled={saving} className="flex-1">{saving ? 'Guardando…' : 'Guardar'}</Button>
      </div>
    </div>
  );
}
