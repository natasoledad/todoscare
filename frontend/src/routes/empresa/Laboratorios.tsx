import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api } from '../../api/client';
import { money } from '../../lib/citas';
import type { LabDental, LabPrestacion } from '../../api/types';

const inputCls = 'w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal';

export function Laboratorios() {
  const navigate = useNavigate();
  const [labs, setLabs] = useState<LabDental[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', rut: '', contacto: '' });
  const [saving, setSaving] = useState(false);
  const [detalle, setDetalle] = useState<LabDental | null>(null);

  const load = () => api.labs.lista().then(setLabs);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    try {
      await api.labs.crear({ nombre: form.nombre.trim(), rut: form.rut.trim() || undefined, contacto: form.contacto.trim() || undefined });
      setOpen(false); setForm({ nombre: '', rut: '', contacto: '' }); await load();
    } finally { setSaving(false); }
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Laboratorios dentales" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        {labs.length === 0 && <div className="text-center text-sm text-sub py-8">Sin laboratorios. Agrega el primero.</div>}
        {labs.map((l) => (
          <div key={l.id} className={`rounded-2xl border border-border bg-white px-4 py-3 ${l.activo ? '' : 'opacity-60'}`}>
            <div className="flex items-center justify-between">
              <div className="font-semibold text-[14px] text-ink">{l.nombre}</div>
              <button onClick={() => setDetalle(l)} className="text-[12px] font-semibold text-teal-dark">Prestaciones ›</button>
            </div>
            <div className="text-[11px] text-sub mt-0.5">{[l.rut, l.contacto].filter(Boolean).join(' · ') || 'Sin datos de contacto'}</div>
            <button onClick={async () => { await api.labs.eliminar(l.id); await load(); }} className="mt-1 text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Nuevo laboratorio</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo laboratorio</div>
          <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre / razón social" className={inputCls} />
          <input value={form.rut} onChange={(e) => setForm((f) => ({ ...f, rut: e.target.value }))} placeholder="RUT (opcional)" className={inputCls} />
          <input value={form.contacto} onChange={(e) => setForm((f) => ({ ...f, contacto: e.target.value }))} placeholder="Contacto (email/teléfono)" className={inputCls} />
          <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear laboratorio'}</Button>
        </BottomSheet>
      )}

      {detalle && <PrestacionesSheet lab={detalle} onClose={() => setDetalle(null)} />}
    </div>
  );
}

function PrestacionesSheet({ lab, onClose }: { lab: LabDental; onClose: () => void }) {
  const [servicios, setServicios] = useState<LabPrestacion[]>([]);
  const [form, setForm] = useState({ nombre: '', costo: '', precio: '' });
  const [saving, setSaving] = useState(false);

  const load = () => api.labs.servicios(lab.id).then(setServicios);
  useEffect(() => { load(); }, [lab.id]);

  const crear = async () => {
    setSaving(true);
    try {
      await api.labs.crearServicio(lab.id, { nombre: form.nombre.trim(), costo: Number(form.costo) || 0, precio: Number(form.precio) || 0 });
      setForm({ nombre: '', costo: '', precio: '' }); await load();
    } finally { setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{lab.nombre}</div>
      <div className="text-[12px] font-semibold text-sub">Prestaciones · costo vs precio</div>
      {servicios.length === 0 && <div className="text-[12px] text-sub">Sin prestaciones aún.</div>}
      <div className="flex flex-col gap-1.5">
        {servicios.map((s) => (
          <div key={s.id} className="rounded-xl bg-[#F6FBF9] px-3 py-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-[13px] text-ink">{s.nombre}</span>
              <button onClick={async () => { await api.labs.eliminarServicio(s.id); await load(); }} className="text-[11px] font-semibold text-danger">Quitar</button>
            </div>
            <div className="flex justify-between text-[11.5px] text-sub mt-0.5 tabular-nums">
              <span>Costo {money(s.costo)}</span>
              <span>Precio {money(s.precio)}</span>
              <span className="text-teal-dark font-semibold">Margen {money(s.margen)}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="text-[12px] font-semibold text-ink mt-2">Agregar prestación</div>
      <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre (ej. Corona de circonio)" className={inputCls} />
      <div className="flex gap-2">
        <input value={form.costo} onChange={(e) => setForm((f) => ({ ...f, costo: e.target.value }))} inputMode="numeric" placeholder="Costo (al lab)" className={inputCls} />
        <input value={form.precio} onChange={(e) => setForm((f) => ({ ...f, precio: e.target.value }))} inputMode="numeric" placeholder="Precio (al paciente)" className={inputCls} />
      </div>
      <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Guardando…' : 'Agregar prestación'}</Button>
    </BottomSheet>
  );
}
