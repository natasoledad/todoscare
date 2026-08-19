import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { AlertasInventario, Bodega, Branch, CentroCosto, InsumoItem, LoteInsumo, MovimientoStock, Proveedor } from '../../api/types';

type Tab = 'insumos' | 'alertas' | 'bodegas' | 'proveedores' | 'centros';
const TABS: { id: Tab; label: string }[] = [
  { id: 'insumos', label: 'Insumos' },
  { id: 'alertas', label: 'Alertas' },
  { id: 'bodegas', label: 'Bodegas' },
  { id: 'proveedores', label: 'Proveedores' },
  { id: 'centros', label: 'Centros de costo' },
];

const inputCls = 'w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal';

const SEMAFORO: Record<string, { dot: string; label: string }> = {
  ok: { dot: 'bg-teal', label: 'OK' },
  bajo: { dot: 'bg-[#E0A100]', label: 'Bajo mínimo' },
  sin_stock: { dot: 'bg-danger', label: 'Sin stock' },
};
const LOTE_ESTADO: Record<string, string> = { vigente: 'Vigente', por_vencer: 'Por vencer', vencido: 'Vencido', sin_vencimiento: 'Sin vencimiento' };
const fechaCorta = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: '2-digit' });

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
        {tab === 'alertas' && <Alertas />}
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
  const [bodegas, setBodegas] = useState<Bodega[]>([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ nombre: '', sku: '', unidad: 'unidad', stock_minimo: '0', supplier_id: '', cost_center_id: '' });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = () => api.inventario.items().then(setItems);
  useEffect(() => {
    load();
    api.inventario.proveedores().then(setProveedores);
    api.inventario.centros().then(setCentros);
    api.inventario.bodegas().then(setBodegas);
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
      {bodegas.length === 0 && <div className="mb-2 rounded-xl bg-warn-bg border border-warn-border px-3 py-2 text-[12px] text-[#8A6A00]">Crea una bodega para poder registrar entradas y salidas.</div>}
      {items.length === 0 && <Empty texto="Aún no hay insumos. Crea el primero." />}
      <div className="flex flex-col gap-2">
        {items.map((it) => <ItemCard key={it.id} item={it} bodegas={bodegas} centros={centros} onChanged={load} />)}
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

function ItemCard({ item, bodegas, centros, onChanged }: { item: InsumoItem; bodegas: Bodega[]; centros: CentroCosto[]; onChanged: () => Promise<void> }) {
  const [sheet, setSheet] = useState<null | 'entrada' | 'salida' | 'kardex'>(null);
  const sem = SEMAFORO[item.estado] ?? SEMAFORO.ok;

  return (
    <div className={`rounded-2xl border border-border bg-white px-4 py-3 ${item.activo ? '' : 'opacity-60'}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`w-2.5 h-2.5 rounded-full ${sem.dot} shrink-0`} title={sem.label} />
          <div className="font-semibold text-[14px] text-ink truncate">{item.nombre}</div>
        </div>
        <span className="text-[13px] font-bold text-ink tabular-nums shrink-0">{item.stock_actual} <span className="font-normal text-sub text-[11px]">{item.unidad}</span></span>
      </div>
      <div className="text-[11px] text-sub mt-0.5">
        {item.sku ? `SKU ${item.sku} · ` : ''}mín {item.stock_minimo} · {item.supplier_nombre || 'Sin proveedor'}{item.cost_center_nombre ? ` · ${item.cost_center_nombre}` : ''}
      </div>
      <div className="mt-2 flex gap-2 flex-wrap">
        <button onClick={() => setSheet('entrada')} className="rounded-lg bg-teal-soft px-3 py-1.5 text-[12px] font-semibold text-teal-dark" disabled={bodegas.length === 0}>+ Entrada</button>
        <button onClick={() => setSheet('salida')} className="rounded-lg bg-[#F6EDEA] px-3 py-1.5 text-[12px] font-semibold text-danger" disabled={bodegas.length === 0}>− Salida</button>
        <button onClick={() => setSheet('kardex')} className="rounded-lg bg-[#EEF2F1] px-3 py-1.5 text-[12px] font-semibold text-sub">Kardex</button>
        <button onClick={async () => { await api.inventario.eliminarItem(item.id); await onChanged(); }} className="ml-auto text-[12px] font-semibold text-danger self-center">Eliminar</button>
      </div>

      {(sheet === 'entrada' || sheet === 'salida') && (
        <MovSheet tipo={sheet} item={item} bodegas={bodegas} centros={centros} onClose={() => setSheet(null)} onDone={async () => { setSheet(null); await onChanged(); }} />
      )}
      {sheet === 'kardex' && <KardexSheet item={item} onClose={() => setSheet(null)} />}
    </div>
  );
}

function MovSheet({ tipo, item, bodegas, centros, onClose, onDone }: { tipo: 'entrada' | 'salida'; item: InsumoItem; bodegas: Bodega[]; centros: CentroCosto[]; onClose: () => void; onDone: () => Promise<void> }) {
  const [warehouseId, setWarehouseId] = useState(bodegas[0]?.id ?? '');
  const [cantidad, setCantidad] = useState('');
  const [lote, setLote] = useState('');
  const [vencimiento, setVencimiento] = useState('');
  const [centroId, setCentroId] = useState('');
  const [motivo, setMotivo] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true); setError(null);
    try {
      const c = Number(cantidad);
      if (tipo === 'entrada') {
        await api.inventario.entrada(item.id, { warehouse_id: warehouseId, cantidad: c, lote: lote.trim() || undefined, vencimiento: vencimiento || undefined, cost_center_id: centroId || undefined, motivo: motivo.trim() || undefined });
      } else {
        await api.inventario.salida(item.id, { warehouse_id: warehouseId, cantidad: c, cost_center_id: centroId || undefined, motivo: motivo.trim() || undefined });
      }
      await onDone();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo registrar'); }
    finally { setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{tipo === 'entrada' ? 'Entrada' : 'Salida'} · {item.nombre}</div>
      <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)} className={inputCls}>
        {bodegas.map((b) => <option key={b.id} value={b.id}>{b.nombre}</option>)}
      </select>
      <input value={cantidad} onChange={(e) => setCantidad(e.target.value)} inputMode="decimal" placeholder={`Cantidad (${item.unidad})`} className={inputCls} />
      {tipo === 'entrada' && (
        <div className="flex gap-2">
          <input value={lote} onChange={(e) => setLote(e.target.value)} placeholder="Lote (opcional)" className={inputCls} />
          <input value={vencimiento} onChange={(e) => setVencimiento(e.target.value)} type="date" className={inputCls} />
        </div>
      )}
      <select value={centroId} onChange={(e) => setCentroId(e.target.value)} className={inputCls}>
        <option value="">Centro de costo (opcional)</option>
        {centros.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
      </select>
      <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo (opcional)" className={inputCls} />
      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={submit} disabled={saving || !warehouseId || !(Number(cantidad) > 0)} className="w-full">{saving ? 'Registrando…' : `Registrar ${tipo}`}</Button>
    </BottomSheet>
  );
}

function KardexSheet({ item, onClose }: { item: InsumoItem; onClose: () => void }) {
  const [lotes, setLotes] = useState<LoteInsumo[]>([]);
  const [movs, setMovs] = useState<MovimientoStock[]>([]);
  useEffect(() => {
    api.inventario.lotes(item.id).then(setLotes);
    api.inventario.movimientos(item.id).then(setMovs);
  }, [item.id]);
  const signo = (m: MovimientoStock) => (m.cantidad > 0 ? 'text-teal-dark' : 'text-danger');

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{item.nombre}</div>
      <div className="text-[12px] font-semibold text-sub">Lotes</div>
      {lotes.filter((l) => l.cantidad > 0).length === 0 && <div className="text-[12px] text-sub">Sin existencias.</div>}
      <div className="flex flex-col gap-1.5">
        {lotes.filter((l) => l.cantidad > 0).map((l) => (
          <div key={l.id} className="flex items-center justify-between rounded-lg bg-[#F6FBF9] px-3 py-2 text-[12.5px]">
            <span className="text-ink">{l.lote || 'Sin lote'} · {l.warehouse_nombre}{l.vencimiento ? ` · vence ${fechaCorta(l.vencimiento)}` : ''}</span>
            <span className={`font-semibold ${l.estado === 'vencido' ? 'text-danger' : l.estado === 'por_vencer' ? 'text-[#B07A00]' : 'text-ink'}`}>{l.cantidad}</span>
          </div>
        ))}
      </div>
      <div className="text-[12px] font-semibold text-sub mt-2">Movimientos</div>
      <div className="flex flex-col gap-1">
        {movs.map((m) => (
          <div key={m.id} className="flex items-center justify-between border-t border-border py-1.5 text-[12.5px]">
            <span className="text-ink capitalize">{m.tipo}{m.motivo ? ` · ${m.motivo}` : ''}<span className="text-[10.5px] text-sub"> · {fechaCorta(m.fecha)}</span></span>
            <span className="text-sub tabular-nums">saldo {m.saldo} · <span className={`font-semibold ${signo(m)}`}>{m.cantidad > 0 ? '+' : ''}{m.cantidad}</span></span>
          </div>
        ))}
      </div>
    </BottomSheet>
  );
}

// ─────────────────────────── Alertas ───────────────────────────
function Alertas() {
  const [al, setAl] = useState<AlertasInventario | null>(null);
  useEffect(() => { api.inventario.alertas().then(setAl); }, []);
  if (!al) return null;
  const nada = al.bajo_minimo.length === 0 && al.lotes_por_vencer.length === 0 && al.lotes_vencidos.length === 0;

  return (
    <div className="flex flex-col gap-4">
      {nada && <Empty texto="Todo en orden: sin alertas de stock ni de vencimiento." />}
      {al.bajo_minimo.length > 0 && (
        <div>
          <div className="font-heading font-bold text-[13px] text-ink mb-2">Bajo el mínimo ({al.bajo_minimo.length})</div>
          <div className="flex flex-col gap-2">
            {al.bajo_minimo.map((it) => (
              <div key={it.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${SEMAFORO[it.estado]?.dot ?? 'bg-danger'}`} />
                  <span className="font-semibold text-[14px] text-ink">{it.nombre}</span>
                </div>
                <span className="text-[12px] text-sub tabular-nums">{it.stock_actual} / mín {it.stock_minimo} {it.unidad}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {al.lotes_vencidos.length > 0 && <LoteAlertList titulo="Lotes vencidos" lotes={al.lotes_vencidos} danger />}
      {al.lotes_por_vencer.length > 0 && <LoteAlertList titulo="Lotes por vencer (30 días)" lotes={al.lotes_por_vencer} />}
    </div>
  );
}

function LoteAlertList({ titulo, lotes, danger }: { titulo: string; lotes: LoteInsumo[]; danger?: boolean }) {
  return (
    <div>
      <div className={`font-heading font-bold text-[13px] mb-2 ${danger ? 'text-danger' : 'text-[#B07A00]'}`}>{titulo} ({lotes.length})</div>
      <div className="flex flex-col gap-2">
        {lotes.map((l) => (
          <div key={l.id} className="flex items-center justify-between rounded-2xl border border-border bg-white px-4 py-3">
            <div>
              <div className="font-semibold text-[13.5px] text-ink">{l.item_nombre}</div>
              <div className="text-[11px] text-sub">{l.lote || 'Sin lote'} · {l.warehouse_nombre}{l.vencimiento ? ` · ${LOTE_ESTADO[l.estado]} ${fechaCorta(l.vencimiento)}` : ''}</div>
            </div>
            <span className="text-[12px] font-semibold text-ink tabular-nums">{l.cantidad}</span>
          </div>
        ))}
      </div>
    </div>
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
