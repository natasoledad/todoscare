import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import type { Encuesta, EncuestaResumen, Plantilla, Tarea } from '../../api/types';

type Tab = 'tareas' | 'encuestas' | 'plantillas';
const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });

export function CrmGestion() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('tareas');

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Gestión CRM" onBack={() => navigate('/empresa')} />
      <div className="px-5 pt-3 flex gap-2 text-[12.5px]">
        {(['tareas', 'encuestas', 'plantillas'] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} className={`rounded-full px-3.5 py-1.5 font-semibold border capitalize ${tab === t ? 'bg-teal text-white border-teal' : 'bg-white text-sub border-border'}`}>{t}</button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24">
        {tab === 'tareas' && <Tareas />}
        {tab === 'encuestas' && <Encuestas />}
        {tab === 'plantillas' && <Plantillas />}
      </div>
    </div>
  );
}

function Tareas() {
  const [lista, setLista] = useState<Tarea[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ titulo: '', descripcion: '' });
  const load = () => api.crm.tareas().then(setLista);
  useEffect(() => { load(); }, []);
  const crear = async () => { await api.crm.crearTarea({ titulo: f.titulo.trim(), descripcion: f.descripcion || undefined }); setOpen(false); setF({ titulo: '', descripcion: '' }); await load(); };
  const toggle = async (t: Tarea) => { await api.crm.actualizarTarea(t.id, { estado: t.estado === 'hecha' ? 'pendiente' : 'hecha' }); await load(); };
  const borrar = async (id: string) => { await api.crm.eliminarTarea(id); await load(); };
  return (
    <>
      <div className="flex flex-col gap-2">
        {lista.length === 0 && <div className="text-center text-sm text-sub py-8">Sin tareas.</div>}
        {lista.map((t) => (
          <div key={t.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-start justify-between gap-2">
              <button onClick={() => toggle(t)} className="text-left flex-1 min-w-0">
                <div className={`font-semibold text-[14px] ${t.estado === 'hecha' ? 'text-sub line-through' : 'text-ink'}`}>{t.estado === 'hecha' ? '✓ ' : '○ '}{t.titulo}</div>
                {t.descripcion && <div className="text-[12px] text-sub mt-0.5">{t.descripcion}</div>}
              </button>
              <button onClick={() => borrar(t.id)} className="text-[11.5px] font-semibold text-danger shrink-0">Eliminar</button>
            </div>
          </div>
        ))}
      </div>
      <FabSheet open={open} setOpen={setOpen} onSave={crear} disabled={!f.titulo.trim()} label="+ Nueva tarea" title="Nueva tarea">
        <input value={f.titulo} onChange={(e) => setF((p) => ({ ...p, titulo: e.target.value }))} placeholder="Título de la tarea" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
        <textarea value={f.descripcion} onChange={(e) => setF((p) => ({ ...p, descripcion: e.target.value }))} placeholder="Descripción (opcional)" rows={3} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
      </FabSheet>
    </>
  );
}

function Encuestas() {
  const [lista, setLista] = useState<Encuesta[]>([]);
  const [resumen, setResumen] = useState<EncuestaResumen | null>(null);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [resp, setResp] = useState<Encuesta | null>(null);
  const [score, setScore] = useState('');
  const [coment, setComent] = useState('');
  const load = () => Promise.all([api.crm.encuestas().then(setLista), api.crm.encuestasResumen().then(setResumen)]);
  useEffect(() => { load(); }, []);
  const enviar = async () => { await api.crm.enviarEncuesta({ paciente_nombre: nombre || undefined }); setOpen(false); setNombre(''); await load(); };
  const responder = async () => { if (!resp) return; await api.crm.responderEncuesta(resp.id, Number(score), coment || undefined); setResp(null); setScore(''); setComent(''); await load(); };
  return (
    <>
      {resumen && (
        <div className="grid grid-cols-2 gap-2 mb-3">
          <Tile label="Respondidas" value={`${resumen.respondidas}/${resumen.enviadas}`} />
          <Tile label="Tasa respuesta" value={`${resumen.tasa_respuesta}%`} />
          <Tile label="Promedio" value={resumen.promedio == null ? '—' : String(resumen.promedio)} />
          <Tile label="NPS" value={resumen.nps == null ? '—' : String(resumen.nps)} tone="good" />
        </div>
      )}
      <div className="flex flex-col gap-2">
        {lista.map((e) => (
          <div key={e.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="font-semibold text-[13.5px] text-ink truncate">{e.paciente_nombre || 'Paciente'}</div>
              {e.estado === 'respondida'
                ? <StatusTag label={`${e.score}/10`} tone="teal" />
                : <button onClick={() => { setResp(e); setScore(''); setComent(''); }} className="text-[12px] font-semibold text-teal-dark">Registrar respuesta</button>}
            </div>
            <div className="text-[11px] text-sub">{fecha(e.fecha)}{e.comentario ? ` · “${e.comentario}”` : ''}</div>
          </div>
        ))}
      </div>
      <FabSheet open={open} setOpen={setOpen} onSave={enviar} disabled={false} label="+ Enviar encuesta" title="Enviar encuesta de satisfacción">
        <div className="text-[12px] text-sub">El envío real por correo/WhatsApp se hará con la integración; por ahora se crea la invitación.</div>
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre del paciente (opcional)" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
      </FabSheet>
      {resp && (
        <BottomSheet onClose={() => setResp(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Respuesta de {resp.paciente_nombre || 'paciente'}</div>
          <div className="text-[12.5px] text-sub">Puntaje 0-10 (¿recomendaría la clínica?)</div>
          <div className="grid grid-cols-6 gap-1.5">
            {Array.from({ length: 11 }, (_, n) => (
              <button key={n} onClick={() => setScore(String(n))} className={`aspect-square rounded-lg border text-[13px] font-bold ${score === String(n) ? 'bg-teal text-white border-teal' : 'bg-white text-ink border-border'}`}>{n}</button>
            ))}
          </div>
          <textarea value={coment} onChange={(e) => setComent(e.target.value)} placeholder="Comentario (opcional)" rows={2} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
          <Button onClick={responder} disabled={score === ''} className="w-full">Guardar respuesta</Button>
        </BottomSheet>
      )}
    </>
  );
}

function Plantillas() {
  const [lista, setLista] = useState<Plantilla[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ nombre: '', canal: 'email', asunto: '', cuerpo: '' });
  const load = () => api.crm.plantillas().then(setLista);
  useEffect(() => { load(); }, []);
  const crear = async () => { await api.crm.crearPlantilla({ nombre: f.nombre.trim(), canal: f.canal, asunto: f.asunto || undefined, cuerpo: f.cuerpo.trim() }); setOpen(false); setF({ nombre: '', canal: 'email', asunto: '', cuerpo: '' }); await load(); };
  const borrar = async (id: string) => { await api.crm.eliminarPlantilla(id); await load(); };
  return (
    <>
      <div className="flex flex-col gap-2">
        {lista.length === 0 && <div className="text-center text-sm text-sub py-8">Sin plantillas.</div>}
        {lista.map((p) => (
          <div key={p.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <div className="font-semibold text-[13.5px] text-ink truncate">{p.nombre}</div>
                <div className="text-[11px] text-sub">{p.canal === 'whatsapp' ? '💬 WhatsApp' : '✉️ Email'}{p.asunto ? ` · ${p.asunto}` : ''}</div>
              </div>
              <button onClick={() => borrar(p.id)} className="text-[11.5px] font-semibold text-danger shrink-0">Eliminar</button>
            </div>
            <div className="mt-1.5 text-[12px] text-sub line-clamp-2">{p.cuerpo}</div>
          </div>
        ))}
      </div>
      <FabSheet open={open} setOpen={setOpen} onSave={crear} disabled={!f.nombre.trim() || !f.cuerpo.trim()} label="+ Nueva plantilla" title="Nueva plantilla">
        <input value={f.nombre} onChange={(e) => setF((p) => ({ ...p, nombre: e.target.value }))} placeholder="Nombre" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
        <select value={f.canal} onChange={(e) => setF((p) => ({ ...p, canal: e.target.value }))} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
          <option value="email">✉️ Email</option>
          <option value="whatsapp">💬 WhatsApp</option>
        </select>
        {f.canal === 'email' && <input value={f.asunto} onChange={(e) => setF((p) => ({ ...p, asunto: e.target.value }))} placeholder="Asunto" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />}
        <textarea value={f.cuerpo} onChange={(e) => setF((p) => ({ ...p, cuerpo: e.target.value }))} placeholder="Cuerpo del mensaje" rows={5} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
      </FabSheet>
    </>
  );
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: 'good' }) {
  return (
    <div className="rounded-2xl border border-border bg-white px-3.5 py-3">
      <div className="text-[11px] text-sub">{label}</div>
      <div className={`mt-0.5 font-heading font-extrabold text-[18px] tabular-nums ${tone === 'good' ? 'text-teal-dark' : 'text-ink'}`}>{value}</div>
    </div>
  );
}

function FabSheet({ open, setOpen, onSave, disabled, label, title, children }: { open: boolean; setOpen: (v: boolean) => void; onSave: () => void; disabled: boolean; label: string; title: string; children: React.ReactNode }) {
  const [saving, setSaving] = useState(false);
  const save = async () => { setSaving(true); try { await onSave(); } finally { setSaving(false); } };
  return (
    <>
      <div className="fixed left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent max-w-[440px] mx-auto">
        <Button onClick={() => setOpen(true)} className="w-full">{label}</Button>
      </div>
      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">{title}</div>
          {children}
          <Button onClick={save} disabled={disabled || saving} className="w-full">{saving ? 'Guardando…' : 'Guardar'}</Button>
        </BottomSheet>
      )}
    </>
  );
}
