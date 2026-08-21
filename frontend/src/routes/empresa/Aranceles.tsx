import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import { money } from '../../lib/citas';
import type { Arancel, ArancelCat, ArancelItem } from '../../api/types';

export function Aranceles() {
  const navigate = useNavigate();
  const [aranceles, setAranceles] = useState<Arancel[]>([]);
  const [sel, setSel] = useState<Arancel | null>(null);
  const [cats, setCats] = useState<ArancelCat[]>([]);
  const [items, setItems] = useState<ArancelItem[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  const loadAranceles = () => api.empresa.aranceles().then(setAranceles);
  useEffect(() => { loadAranceles(); }, []);
  const abrir = async (a: Arancel) => {
    setSel(a); setMsg(null);
    const [c, i] = await Promise.all([api.empresa.arancelCategorias(a.id), api.empresa.arancelItems(a.id)]);
    setCats(c); setItems(i);
  };
  const recargar = async () => {
    if (!sel) return;
    const [c, i] = await Promise.all([api.empresa.arancelCategorias(sel.id), api.empresa.arancelItems(sel.id)]);
    setCats(c); setItems(i);
    await loadAranceles();
  };

  // ── sheets ──
  const [sheet, setSheet] = useState<null | 'arancel' | 'item' | 'cat' | 'inc' | 'import'>(null);
  const [importTxt, setImportTxt] = useState('');
  const [importRes, setImportRes] = useState<{ creados: number; actualizados: number; total_filas: number; errores: { fila: number; motivo: string }[] } | null>(null);

  const importar = async () => {
    if (!sel || !importTxt.trim()) return;
    setSaving(true); setErr(null);
    try { const r = await api.empresa.importarArancel(sel.id, importTxt); setImportRes(r); await recargar(); }
    catch (e) { setErr(e instanceof ApiError ? String(e.detail) : 'No se pudo importar.'); }
    finally { setSaving(false); }
  };
  const onCsvFile = (file: File) => { const r = new FileReader(); r.onload = () => setImportTxt(String(r.result)); r.readAsText(file); };
  const [aNombre, setANombre] = useState(''); const [aTipo, setATipo] = useState('particular'); const [aBase, setABase] = useState(false);
  const [cNombre, setCNombre] = useState('');
  const [pct, setPct] = useState('10');
  const [it, setIt] = useState({ categoria_id: '', codigo: '', nombre: '', precio: '', precio_referencia: '', permite_descuento: true, comisiona: true });
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const crearArancel = async () => {
    setSaving(true); setErr(null);
    try {
      await api.empresa.crearArancel({ nombre: aNombre, tipo: aTipo, es_base: aBase });
      setANombre(''); setATipo('particular'); setABase(false); setSheet(null);
      await loadAranceles();
    } catch (e) { setErr(e instanceof ApiError ? String(e.detail) : 'No se pudo crear'); } finally { setSaving(false); }
  };
  const crearItem = async () => {
    if (!sel) return;
    setSaving(true); setErr(null);
    try {
      await api.empresa.crearArancelItem(sel.id, {
        categoria_id: it.categoria_id || null, codigo: it.codigo || null, nombre: it.nombre,
        precio: Number(it.precio) || 0, precio_referencia: it.precio_referencia ? Number(it.precio_referencia) : null,
        permite_descuento: it.permite_descuento, comisiona: it.comisiona,
      });
      setIt({ categoria_id: '', codigo: '', nombre: '', precio: '', precio_referencia: '', permite_descuento: true, comisiona: true });
      setSheet(null); await recargar();
    } catch (e) { setErr(e instanceof ApiError ? String(e.detail) : 'No se pudo crear la prestación'); } finally { setSaving(false); }
  };
  const crearCat = async () => {
    if (!sel) return;
    setSaving(true);
    await api.empresa.crearCategoria(sel.id, { nombre: cNombre });
    setCNombre(''); setSheet(null); await recargar(); setSaving(false);
  };
  const incrementar = async () => {
    if (!sel) return;
    setSaving(true);
    const r = await api.empresa.incrementarArancel(sel.id, Number(pct) / 100);
    setSheet(null); setMsg(`Se ajustaron ${r.afectados} precio(s) en ${pct}%.`); await recargar(); setSaving(false);
  };
  const copiarBase = async () => {
    if (!sel) return;
    try {
      const r = await api.empresa.copiarArancelBase(sel.id);
      setMsg(`Se copiaron ${r.copiados} prestación(es) del arancel base.`); await recargar();
    } catch (e) { setMsg(e instanceof ApiError ? String(e.detail) : 'No se pudo copiar'); }
  };
  const eliminarItem = async (id: string) => { await api.empresa.eliminarArancelItem(id); await recargar(); };
  const eliminarArancel = async (id: string) => { await api.empresa.eliminarArancel(id); setSel(null); await loadAranceles(); };

  const tipoLabel = (t: string) => (t === 'base' ? 'Base' : t === 'empresa' ? 'Empresa' : 'Particular');

  // ─────────── NIVEL 1: lista de aranceles ───────────
  if (!sel) {
    return (
      <div className="h-full flex flex-col relative">
        <BackHeader title="Aranceles" onBack={() => navigate('/empresa')} />
        <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
          {aranceles.length === 0 && <div className="text-center text-sm text-sub py-8">Sin aranceles. Crea el arancel base y luego los particulares/por empresa.</div>}
          {aranceles.map((a) => (
            <div key={a.id} onClick={() => abrir(a)} className={`flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5 cursor-pointer ${a.activo ? '' : 'opacity-60'}`}>
              <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">💲</div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-ink">{a.nombre}{a.es_base && <span className="ml-1.5 rounded-full bg-teal-soft text-teal-dark px-2 py-0.5 text-[10px] font-bold">BASE</span>}</div>
                <div className="mt-0.5 text-xs text-sub">{tipoLabel(a.tipo)} · {a.n_items} prestación(es)</div>
              </div>
              <div className="text-[13px] text-sub">›</div>
            </div>
          ))}
        </div>
        <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
          <Button onClick={() => { setErr(null); setSheet('arancel'); }} className="w-full">+ Nuevo arancel</Button>
        </div>
        {sheet === 'arancel' && (
          <BottomSheet onClose={() => setSheet(null)}>
            <div className="font-heading font-extrabold text-[17px] text-ink">Nuevo arancel</div>
            <input value={aNombre} onChange={(e) => setANombre(e.target.value)} placeholder="Nombre (ej. Particular, Convenio X)"
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <select value={aTipo} onChange={(e) => setATipo(e.target.value)}
              className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
              <option value="particular">Particular</option>
              <option value="base">Base</option>
              <option value="empresa">Empresa / convenio</option>
            </select>
            <label className="flex items-center gap-2 text-[12.5px] text-ink">
              <input type="checkbox" checked={aBase} onChange={(e) => setABase(e.target.checked)} className="accent-teal" />
              Es el arancel base (del que heredan los demás)
            </label>
            {err && <div className="text-xs text-danger">{err}</div>}
            <Button onClick={crearArancel} disabled={!aNombre || saving} className="w-full">Crear arancel</Button>
          </BottomSheet>
        )}
      </div>
    );
  }

  // ─────────── NIVEL 2: detalle del arancel ───────────
  const itemsByCat = (cid: string | null) => items.filter((i) => (i.categoria_id ?? null) === cid);
  const sinCat = itemsByCat(null);

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title={sel.nombre} onBack={() => setSel(null)} />
      <div className="px-5 pt-2 flex flex-wrap gap-1.5">
        <button onClick={() => { setErr(null); setSheet('item'); }} className="rounded-full bg-teal text-white px-3 py-1.5 text-[12px] font-semibold">+ Prestación</button>
        <button onClick={() => setSheet('cat')} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink">+ Categoría</button>
        <button onClick={() => setSheet('inc')} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink">Incrementar %</button>
        <button onClick={() => { setImportTxt(''); setImportRes(null); setSheet('import'); }} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink">Importar CSV</button>
        {!sel.es_base && <button onClick={copiarBase} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink">Copiar del base</button>}
        <button onClick={() => eliminarArancel(sel.id)} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-danger">Eliminar arancel</button>
      </div>
      {msg && <div className="px-5 pt-2 text-[12px] text-teal-dark">{msg}</div>}

      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-3">
        {items.length === 0 && <div className="text-center text-sm text-sub py-8">Sin prestaciones. Agrega la primera{sel.es_base ? '' : ' o cópialas del arancel base'}.</div>}
        {cats.map((c) => {
          const list = itemsByCat(c.id);
          if (list.length === 0) return null;
          return (
            <div key={c.id}>
              <div className="text-[12px] font-heading font-bold text-ink pb-1">{c.nombre}</div>
              <div className="rounded-2xl border border-border bg-white">
                {list.map((i, idx) => <ItemRow key={i.id} i={i} first={idx === 0} onDel={eliminarItem} />)}
              </div>
            </div>
          );
        })}
        {sinCat.length > 0 && (
          <div>
            <div className="text-[12px] font-heading font-bold text-sub pb-1">Sin categoría</div>
            <div className="rounded-2xl border border-border bg-white">
              {sinCat.map((i, idx) => <ItemRow key={i.id} i={i} first={idx === 0} onDel={eliminarItem} />)}
            </div>
          </div>
        )}
      </div>

      {sheet === 'item' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva prestación</div>
          <div className="flex gap-2">
            <input value={it.codigo} onChange={(e) => setIt({ ...it, codigo: e.target.value })} placeholder="Código" className="w-24 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={it.nombre} onChange={(e) => setIt({ ...it, nombre: e.target.value })} placeholder="Nombre de la prestación" className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <select value={it.categoria_id} onChange={(e) => setIt({ ...it, categoria_id: e.target.value })} className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            <option value="">Sin categoría</option>
            {cats.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select>
          <div className="flex gap-2">
            <input value={it.precio} onChange={(e) => setIt({ ...it, precio: e.target.value })} inputMode="numeric" placeholder="Precio" className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={it.precio_referencia} onChange={(e) => setIt({ ...it, precio_referencia: e.target.value })} inputMode="numeric" placeholder="Precio ref. (opc.)" className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <label className="flex items-center gap-2 text-[12.5px] text-ink"><input type="checkbox" checked={it.permite_descuento} onChange={(e) => setIt({ ...it, permite_descuento: e.target.checked })} className="accent-teal" /> Permite descuento</label>
          <label className="flex items-center gap-2 text-[12.5px] text-ink"><input type="checkbox" checked={it.comisiona} onChange={(e) => setIt({ ...it, comisiona: e.target.checked })} className="accent-teal" /> Comisiona al profesional</label>
          {err && <div className="text-xs text-danger">{err}</div>}
          <Button onClick={crearItem} disabled={!it.nombre || saving} className="w-full">Agregar prestación</Button>
        </BottomSheet>
      )}
      {sheet === 'cat' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Nueva categoría</div>
          <input value={cNombre} onChange={(e) => setCNombre(e.target.value)} placeholder="Nombre (ej. Cirugía, Insumos)" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <Button onClick={crearCat} disabled={!cNombre || saving} className="w-full">Crear categoría</Button>
        </BottomSheet>
      )}
      {sheet === 'inc' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Incrementar precios</div>
          <div className="text-[12.5px] text-sub">Ajusta todas las prestaciones de este arancel por un porcentaje. Usa negativo para bajar.</div>
          <input value={pct} onChange={(e) => setPct(e.target.value)} inputMode="numeric" placeholder="% (ej. 10 o -5)" className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <Button onClick={incrementar} disabled={saving} className="w-full">Aplicar {pct}%</Button>
        </BottomSheet>
      )}
      {sheet === 'import' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Importar prestaciones (CSV)</div>
          <div className="text-[12px] text-sub">Columnas: <b>código, nombre, precio, categoría, precio_referencia</b>. La primera fila son los títulos. Autocrea categorías; si el código ya existe, actualiza.</div>
          <label className="text-[12.5px] font-semibold text-teal-dark cursor-pointer">
            Elegir archivo .csv
            <input type="file" accept=".csv,text/csv,text/plain" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) onCsvFile(f); }} />
          </label>
          <textarea value={importTxt} onChange={(e) => setImportTxt(e.target.value)} rows={6} placeholder={'codigo,nombre,precio,categoria\nCB01,Consulta,25000,Consultas'}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-[12.5px] font-mono text-ink outline-none focus:border-teal resize-none" />
          {err && <div className="text-xs text-danger">{err}</div>}
          {importRes && (
            <div className="rounded-xl bg-[#F6FBF9] px-3 py-2.5 text-[12.5px] text-ink">
              ✅ {importRes.creados} creadas · {importRes.actualizados} actualizadas (de {importRes.total_filas} filas).
              {importRes.errores.length > 0 && (
                <div className="mt-1 text-danger text-[11.5px]">{importRes.errores.length} con error: {importRes.errores.slice(0, 3).map((e) => `fila ${e.fila}`).join(', ')}{importRes.errores.length > 3 ? '…' : ''}</div>
              )}
            </div>
          )}
          <Button onClick={importar} disabled={saving || !importTxt.trim()} className="w-full">{saving ? 'Importando…' : 'Importar'}</Button>
        </BottomSheet>
      )}
    </div>
  );
}

function ItemRow({ i, first, onDel }: { i: ArancelItem; first: boolean; onDel: (id: string) => void }) {
  return (
    <div className={`flex items-center justify-between px-4 py-2.5 ${first ? '' : 'border-t border-[#F2F6F5]'}`}>
      <div className="min-w-0">
        <div className="text-[13px] text-ink truncate">{i.codigo ? <span className="font-mono text-[11px] text-sub">{i.codigo} </span> : ''}{i.nombre}</div>
        <div className="mt-0.5 flex gap-1.5">
          {!i.permite_descuento && <span className="rounded-full bg-[#EEF2F1] text-sub px-1.5 py-0.5 text-[10px]">Sin dscto</span>}
          {!i.comisiona && <span className="rounded-full bg-[#EEF2F1] text-sub px-1.5 py-0.5 text-[10px]">No comisiona</span>}
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-2">
        <div className="text-[13px] font-semibold text-ink tabular-nums">{money(i.precio)}</div>
        <button onClick={() => onDel(i.id)} className="text-[11px] font-bold text-danger">Baja</button>
      </div>
    </div>
  );
}
