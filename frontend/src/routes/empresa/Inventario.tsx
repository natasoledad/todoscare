import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { Bodega, Branch, CentroCosto, InsumoItem, Proveedor } from '../../api/types';

type Tab = 'insumos' | 'bodegas' | 'proveedores' | 'centros';
const TABS: { id: Tab; label: string }[] = [
  { id: 'insumos', label: 'Insumos' },
  { id: 'bodegas', label: 'Bodegas' },
  { id: 'proveedores', label: 'Proveedores' },
  { id: 'centros', label: 'Centros de costo' },
];

const inputCls = 'w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal';

export function Inventario() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('insumos');

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Inventario" onBack={() => navigate('/empresa')} />
      <div className="px-5 pt-3">
        <div className="flex gap-1.5 overflow-x-auto scrollhide pb-1">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`whitespace-nowrap rounded-full px-3.5 py-1.5 text-[12.5px] font-semibold ${tab === t.id ? 'bg-teal text-white' : 'bg-[#EEF2F1] text-sub'}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24">
        {tab === 'insumos' && <Insumos />}
        {tab === 'bodegas' && <Bodegas />}
        {tab === 'proveedores' && <Proveedores />}
        {tab === 'centros' && <Centros />}
      </div>
    </div>
  );
}

// ─────────────────────────── Insumos ───────────────────────────
function Insumos() {
  const [items, setItems] = useState<InsumoItem[]>([]);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [centros, setCentros] = useState<CentroCosto[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', sku: '', unidad: 'unidad', stock_minimo: '0', supplier_id: '', cost_center_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.inventario.items().then(setItems);
  useEffect(() => {
    load();
    api.inventario.proveedores().then(setProveedores);
    api.inventario.centros().then(setCentros);
  }, []);

  const crear = async () => {
    setSaving(true); setError(null);
    try {
      await api.inventario.crearItem({
        nombre: form.nombre.trim(), sku: form.sku.trim() || undefined, unidad: form.unidad.trim() || 'unidad',
        stock_minimo: Number(form.stock_minimo) || 0,
        supplier_id: form.supplier_id || undefined, cost_center_id: form.cost_center_id || undefined,
      });
      setOpen(false); setForm({ nombre: '', sku: '', unidad: 'unidad', stock_minimo: '0', supplier_id: '', cost_center_id: '' });
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo crear el insumo'); }
    finally { setSaving(false); }
  };

  return (
    <>
      <SectionHead titulo="Insumos" onNew={() => { setOpen(true); setError(null); }} />
      {items.length === 0 && <Empty texto="Aún no hay insumos. Crea el primero." />}
      <div className="flex flex-col gap-2">
        {items.map((it) => (
          <div key={it.id} className={`rounded-2xl border border-border bg-white px-4 py-3 ${it.activo ? '' : 'opacity-60'}`}>
            <div className="flex items-center justify-between">
              <div className="font-semibold text-[14px] text-ink">{it.nombre}</div>
              <span className="text-[11px] text-sub tabular-nums">mín {it.stock_minimo} {it.unidad}</span>
            </div>
            <div className="text-[11px] text-sub mt-0.5">
              {it.sku ? `SKU ${it.sku} · ` : ''}{it.supplier_nombre || 'Sin proveedor'}{it.cost_center_nombre ? ` · ${it.cost_center_nombre}` : ''}
            </div>
            <button onClick={async () => { await api.inventario.eliminarItem(it.id); await load(); }} className="mt-1 text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo insumo</div>
          <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre (ej. Guantes de nitrilo M)" className={inputCls} />
          <div className="flex gap-2">
            <input value={form.sku} onChange={(e) => setForm((f) => ({ ...f, sku: e.target.value }))} placeholder="SKU (opcional)" className={inputCls} />
            <input value={form.unidad} onChange={(e) => setForm((f) => ({ ...f, unidad: e.target.value }))} placeholder="Unidad" className={inputCls} />
          </div>
          <div>
            <label className="text-[12px] font-semibold text-sub">Stock mínimo (semáforo)</label>
            <input value={form.stock_minimo} onChange={(e) => setForm((f) => ({ ...f, stock_minimo: e.target.value }))} inputMode="numeric" className={`${inputCls} mt-1`} />
          </div>
          <select value={form.supplier_id} onChange={(e) => setForm((f) => ({ ...f, supplier_id: e.target.value }))} className={inputCls}>
            <option value="">Proveedor (opcional)</option>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
          <select value={form.cost_center_id} onChange={(e) => setForm((f) => ({ ...f, cost_center_id: e.target.value }))} className={inputCls}>
            <option value="">Centro de costo (opcional)</option>
            {centros.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear insumo'}</Button>
        </BottomSheet>
      )}
    </>
  );
}

// ─────────────────────────── Bodegas ───────────────────────────
function Bodegas() {
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [branchId, setBranchId] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => api.inventario.bodegas().then(setBodegas);
  useEffect(() => { load(); api.empresa.sucursales().then(setBranches); }, []);

  const crear = async () => {
    setSaving(true);
    try {
      await api.inventario.crearBodega({ nombre: nombre.trim(), branch_id: branchId || undefined });
      setOpen(false); setNombre(''); setBranchId(''); await load();
    } finally { setSaving(false); }
  };

  return (
    <>
      <SectionHead titulo="Bodegas" onNew={() => setOpen(true)} />
      {bodegas.length === 0 && <Empty texto="Sin bodegas. Crea una central o por sucursal." />}
      <div className="flex flex-col gap-2">
        {bodegas.map((b) => (
          <div key={b.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[14px] text-ink">{b.nombre}</div>
              <div className="text-[11px] text-sub">{b.branch_nombre || 'Central (todas las sucursales)'}</div>
            </div>
            <button onClick={async () => { await api.inventario.eliminarBodega(b.id); await load(); }} className="text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva bodega</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Bodega Central)" className={inputCls} />
          <select value={branchId} onChange={(e) => setBranchId(e.target.value)} className={inputCls}>
            <option value="">Central (todas las sucursales)</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
          </select>
          <Button onClick={crear} disabled={saving || !nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear bodega'}</Button>
        </BottomSheet>
      )}
    </>
  );
}

// ─────────────────────────── Proveedores ───────────────────────────
function Proveedores() {
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', rut: '', contacto: '' });
  const [saving, setSaving] = useState(false);

  const load = () => api.inventario.proveedores().then(setProveedores);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    try {
      await api.inventario.crearProveedor({ nombre: form.nombre.trim(), rut: form.rut.trim() || undefined, contacto: form.contacto.trim() || undefined });
      setOpen(false); setForm({ nombre: '', rut: '', contacto: '' }); await load();
    } finally { setSaving(false); }
  };

  return (
    <>
      <SectionHead titulo="Proveedores" onNew={() => setOpen(true)} />
      {proveedores.length === 0 && <Empty texto="Sin proveedores." />}
      <div className="flex flex-col gap-2">
        {proveedores.map((p) => (
          <div key={p.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[14px] text-ink">{p.nombre}</div>
              <div className="text-[11px] text-sub">{[p.rut, p.contacto].filter(Boolean).join(' · ') || 'Sin datos de contacto'}</div>
            </div>
            <button onClick={async () => { await api.inventario.eliminarProveedor(p.id); await load(); }} className="text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo proveedor</div>
          <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} placeholder="Nombre / razón social" className={inputCls} />
          <input value={form.rut} onChange={(e) => setForm((f) => ({ ...f, rut: e.target.value }))} placeholder="RUT (opcional)" className={inputCls} />
          <input value={form.contacto} onChange={(e) => setForm((f) => ({ ...f, contacto: e.target.value }))} placeholder="Contacto (email/teléfono)" className={inputCls} />
          <Button onClick={crear} disabled={saving || !form.nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear proveedor'}</Button>
        </BottomSheet>
      )}
    </>
  );
}

// ─────────────────────────── Centros de costo ───────────────────────────
function Centros() {
  const [centros, setCentros] = useState<CentroCosto[]>([]);
  const [open, setOpen] = useState(false);
  const [nombre, setNombre] = useState('');
  const [saving, setSaving] = useState(false);

  const load = () => api.inventario.centros().then(setCentros);
  useEffect(() => { load(); }, []);

  const crear = async () => {
    setSaving(true);
    try { await api.inventario.crearCentro({ nombre: nombre.trim() }); setOpen(false); setNombre(''); await load(); }
    finally { setSaving(false); }
  };

  return (
    <>
      <SectionHead titulo="Centros de costo" onNew={() => setOpen(true)} />
      {centros.length === 0 && <Empty texto="Sin centros de costo." />}
      <div className="flex flex-col gap-2">
        {centros.map((c) => (
          <div key={c.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div className="font-semibold text-[14px] text-ink">{c.nombre}</div>
            <button onClick={async () => { await api.inventario.eliminarCentro(c.id); await load(); }} className="text-[12px] font-semibold text-danger">Eliminar</button>
          </div>
        ))}
      </div>
      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo centro de costo</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej. Esterilización)" className={inputCls} />
          <Button onClick={crear} disabled={saving || !nombre.trim()} className="w-full">{saving ? 'Creando…' : 'Crear centro'}</Button>
        </BottomSheet>
      )}
    </>
  );
}

// ─────────────────────────── helpers UI ───────────────────────────
function SectionHead({ titulo, onNew }: { titulo: string; onNew: () => void }) {
  return (
    <div className="flex items-center justify-between mb-2.5">
      <div className="font-heading font-bold text-[14px] text-ink">{titulo}</div>
      <button onClick={onNew} className="text-[12.5px] font-semibold text-teal-dark">+ Nuevo</button>
    </div>
  );
}

function Empty({ texto }: { texto: string }) {
  return <div className="text-center text-sm text-sub py-8">{texto}</div>;
}
