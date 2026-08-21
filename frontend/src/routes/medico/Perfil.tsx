import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { useAuth } from '../../context/AuthContext';
import { api, ApiError } from '../../api/client';
import type { CampoFicha, FichaEsp } from '../../api/types';

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

      <FichasEspCard />

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

// ─────────────────────── Fichas por especialidad (71.7) ───────────────────────
const TIPOS: { v: string; label: string }[] = [
  { v: 'texto', label: 'Texto' }, { v: 'area', label: 'Texto largo' }, { v: 'numero', label: 'Número' },
  { v: 'opcion', label: 'Opción' }, { v: 'checkbox', label: 'Sí/No' },
];

function FichasEspCard() {
  const [lista, setLista] = useState<FichaEsp[]>([]);
  const [edit, setEdit] = useState<FichaEsp | 'nuevo' | null>(null);

  const load = () => api.medico.fichasEspecialidad().then(setLista).catch(() => setLista([]));
  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="px-5 pt-5 flex items-center justify-between">
        <div className="font-heading font-bold text-[13px] text-ink">Fichas por especialidad</div>
        <button onClick={() => setEdit('nuevo')} className="text-[12.5px] font-semibold text-teal-dark">+ Nueva</button>
      </div>
      <div className="mx-5 mt-2.5 flex flex-col gap-2">
        {lista.length === 0 && <div className="text-[12.5px] text-sub">Definí campos propios de tu especialidad para completarlos en la atención.</div>}
        {lista.map((f) => (
          <button key={f.id} onClick={() => setEdit(f)} className="text-left rounded-2xl border border-border bg-white px-4 py-3">
            <div className="font-semibold text-[14px] text-ink">{f.nombre}</div>
            <div className="text-[11.5px] text-sub mt-0.5">{f.campos.length} campo(s){f.activo ? '' : ' · inactiva'}</div>
          </button>
        ))}
      </div>
      {edit && <FichaEspEditor ficha={edit === 'nuevo' ? null : edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); load(); }} />}
    </>
  );
}

function FichaEspEditor({ ficha, onClose, onSaved }: { ficha: FichaEsp | null; onClose: () => void; onSaved: () => void }) {
  const nuevo = ficha === null;
  const [nombre, setNombre] = useState(ficha?.nombre ?? '');
  const [campos, setCampos] = useState<CampoFicha[]>(ficha?.campos ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slug = (s: string) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40) || 'campo';
  const addCampo = () => setCampos((p) => [...p, { clave: `campo_${p.length + 1}`, label: '', tipo: 'texto' }]);
  const setCampo = (i: number, patch: Partial<CampoFicha>) => setCampos((p) => p.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const delCampo = (i: number) => setCampos((p) => p.filter((_, j) => j !== i));

  const guardar = async () => {
    setSaving(true); setError(null);
    const limpio = campos.filter((c) => c.label.trim()).map((c) => ({ ...c, clave: c.clave || slug(c.label), opciones: c.tipo === 'opcion' ? (c.opciones ?? []).filter(Boolean) : undefined }));
    try {
      if (nuevo) await api.medico.crearFichaEsp({ nombre, campos: limpio });
      else await api.medico.editarFichaEsp(ficha!.id, { nombre, campos: limpio });
      onSaved();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.'); setSaving(false); }
  };
  const eliminar = async () => { if (!ficha) return; setSaving(true); try { await api.medico.eliminarFichaEsp(ficha.id); onSaved(); } catch { setSaving(false); } };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{nuevo ? 'Nueva ficha' : 'Editar ficha'}</div>
      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (p. ej. Ficha cardiología)"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      <div className="text-[12px] font-semibold text-ink">Campos</div>
      <div className="flex flex-col gap-2 max-h-[42vh] overflow-y-auto scrollhide">
        {campos.map((c, i) => (
          <div key={i} className="rounded-xl border border-border p-2.5 flex flex-col gap-1.5">
            <div className="flex gap-1.5">
              <input value={c.label} onChange={(e) => setCampo(i, { label: e.target.value, clave: c.clave || slug(e.target.value) })} placeholder="Etiqueta"
                className="flex-1 min-w-0 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[13px] text-ink outline-none focus:border-teal" />
              <select value={c.tipo} onChange={(e) => setCampo(i, { tipo: e.target.value })} className="w-28 rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12px] text-ink outline-none focus:border-teal">
                {TIPOS.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
              </select>
              <button onClick={() => delCampo(i)} className="text-[11px] font-semibold text-danger px-1">✕</button>
            </div>
            {c.tipo === 'opcion' && (
              <input value={(c.opciones ?? []).join(', ')} onChange={(e) => setCampo(i, { opciones: e.target.value.split(',').map((s) => s.trim()) })} placeholder="Opciones separadas por coma"
                className="w-full rounded-lg border-[1.5px] border-border-strong bg-white px-2 py-2 text-[12.5px] text-ink outline-none focus:border-teal" />
            )}
          </div>
        ))}
        <button onClick={addCampo} className="text-[12.5px] font-semibold text-teal-dark py-1 text-left">+ Agregar campo</button>
      </div>
      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={guardar} disabled={saving || !nombre} className="w-full">{saving ? 'Guardando…' : nuevo ? 'Crear ficha' : 'Guardar'}</Button>
      {!nuevo && <button onClick={eliminar} disabled={saving} className="w-full text-[12.5px] font-semibold text-danger py-1">Eliminar ficha</button>}
    </BottomSheet>
  );
}
