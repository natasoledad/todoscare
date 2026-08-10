import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { BottomSheet } from '../../components/BottomSheet';
import { Button } from '../../components/Button';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { TributarioTipos, TaxEmisor, TaxFolio, TaxDocResumen, TaxDoc } from '../../api/types';

const TIPO_LABEL: Record<string, string> = {
  boleta_electronica: 'Boleta electrónica (39)',
  factura_electronica: 'Factura electrónica (33)',
  nota_credito: 'Nota de crédito (61)',
  nfse: 'NFS-e (serviço)',
  nfe: 'NF-e (mercadoria)',
  nfce: 'NFC-e (consumidor)',
};
const tipoLabel = (t: string) => TIPO_LABEL[t] ?? t;

const estadoTone = (e: string): 'teal' | 'warn' | 'danger' | 'muted' =>
  e === 'aceptado' ? 'teal' : e === 'rechazado' ? 'danger' : e === 'anulado' ? 'muted' : 'warn';

const fmt = (monto: number, moneda: string) => {
  try {
    return new Intl.NumberFormat(moneda === 'BRL' ? 'pt-BR' : 'es-CL', { style: 'currency', currency: moneda, maximumFractionDigits: moneda === 'CLP' ? 0 : 2 }).format(monto);
  } catch {
    return `${monto} ${moneda}`;
  }
};
const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: '2-digit' });

export function Tributario() {
  const navigate = useNavigate();
  const [tipos, setTipos] = useState<TributarioTipos | null>(null);
  const [emisor, setEmisor] = useState<TaxEmisor | null>(null);
  const [folios, setFolios] = useState<TaxFolio[]>([]);
  const [docs, setDocs] = useState<TaxDocResumen[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [sheet, setSheet] = useState<null | 'emitir' | 'emisor'>(null);
  const [detalle, setDetalle] = useState<TaxDoc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // form emitir
  const [form, setForm] = useState({ tipo_documento: '', descripcion: '', cantidad: '1', precio: '', receptor_tax_id: '', receptor_nombre: '', serie: '' });
  // form emisor
  const [em, setEm] = useState({ tax_id: '', razon_social: '', giro: '', direccion: '' });

  const load = async () => {
    const t = await api.tributario.tipos();
    setTipos(t);
    const [e, f, d] = await Promise.all([api.tributario.emisor(), api.tributario.folios(), api.tributario.documentos()]);
    setEmisor(e);
    setFolios(f);
    setDocs(d);
    setForm((p) => ({ ...p, tipo_documento: p.tipo_documento || t.tipos[0] || '', serie: t.pais === 'BR' ? (t.tipos[0] === 'nfse' ? 'RPS' : '1') : '' }));
    setLoaded(true);
  };
  useEffect(() => { load(); }, []);

  const abrirEmisor = () => {
    setEm({ tax_id: emisor?.tax_id ?? '', razon_social: emisor?.razon_social ?? '', giro: emisor?.giro ?? '', direccion: emisor?.direccion ?? '' });
    setError(null); setSheet('emisor');
  };

  const guardarEmisor = async () => {
    setSaving(true); setError(null);
    try {
      await api.tributario.guardarEmisor({ tax_id: em.tax_id, razon_social: em.razon_social, giro: em.giro || undefined, direccion: em.direccion || undefined, config: emisor?.config ?? undefined });
      setSheet(null);
      await load();
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar el emisor'); }
    finally { setSaving(false); }
  };

  const emitir = async () => {
    setSaving(true); setError(null);
    try {
      const esBR = tipos?.pais === 'BR';
      const doc = await api.tributario.emitir({
        tipo_documento: form.tipo_documento,
        items: [{ descripcion: form.descripcion || 'Atención', cantidad: Number(form.cantidad) || 1, precio_unitario: Number(form.precio) || 0 }],
        receptor: form.receptor_tax_id || form.receptor_nombre ? { tax_id: form.receptor_tax_id || undefined, nombre: form.receptor_nombre || undefined } : undefined,
        serie: esBR ? (form.serie || undefined) : undefined,
      });
      setSheet(null);
      setForm((p) => ({ ...p, descripcion: '', precio: '', receptor_tax_id: '', receptor_nombre: '' }));
      await load();
      setDetalle(doc);
    } catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo emitir'); }
    finally { setSaving(false); }
  };

  const anular = async (id: string) => {
    const motivo = window.prompt('Motivo de la anulación:');
    if (!motivo) return;
    try {
      await api.tributario.anular(id, motivo);
      await load();
      setDetalle(null);
    } catch (e) { window.alert(e instanceof ApiError ? String(e.detail) : 'No se pudo anular'); }
  };

  const paisNombre = tipos?.pais === 'CL' ? 'Chile · SII' : tipos?.pais === 'BR' ? 'Brasil · Nota Fiscal' : (tipos?.pais ?? '—');

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Documentos tributarios" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-3">

        {loaded && tipos && !tipos.habilitado && (
          <div className="rounded-2xl border border-border bg-[#FFF8EC] px-4 py-4 text-[12.5px] text-ink">
            El conector <strong>tributario</strong> no está habilitado para esta clínica. Pídele al administrador que lo active en Integraciones.
          </div>
        )}

        {/* Emisor fiscal */}
        <div className="rounded-2xl border border-border bg-white px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="text-[12px] font-semibold text-sub">Emisor fiscal · {paisNombre}</div>
            <button onClick={abrirEmisor} className="text-[12px] font-semibold text-teal">{emisor ? 'Editar' : 'Configurar'}</button>
          </div>
          {emisor ? (
            <div className="mt-1">
              <div className="font-heading font-bold text-[15px] text-ink">{emisor.razon_social}</div>
              <div className="text-[12px] text-sub">{tipos?.pais === 'BR' ? 'CNPJ' : 'RUT'} {emisor.tax_id}{emisor.giro ? ` · ${emisor.giro}` : ''}</div>
            </div>
          ) : (
            <div className="mt-1 text-[12.5px] text-sub">Aún no configuras el emisor. Es necesario para emitir documentos.</div>
          )}
        </div>

        {/* Folios / CAF */}
        {folios.length > 0 && (
          <div className="rounded-2xl border border-border bg-white">
            <div className="px-4 pt-3 pb-1 text-[12px] font-semibold text-ink">Folios disponibles</div>
            {folios.map((f) => (
              <div key={f.id} className="flex items-center justify-between px-4 py-2.5 border-t border-[#F2F6F5]">
                <div className="text-[13px] text-ink">{tipoLabel(f.tipo_documento)}{f.serie ? ` · serie ${f.serie}` : ''}</div>
                <div className="text-[12px] text-sub tabular-nums">{f.disponibles.toLocaleString('es-CL')} folios · próximo #{f.siguiente}</div>
              </div>
            ))}
          </div>
        )}

        {/* Emitir */}
        <Button onClick={() => { setError(null); setSheet('emitir'); }} disabled={!emisor} className="w-full">Emitir documento</Button>

        {/* Documentos */}
        <div className="px-1 pt-2 text-[13px] font-heading font-bold text-ink">Documentos emitidos</div>
        {loaded && docs.length === 0 && <div className="text-center text-sm text-sub py-4">Aún no hay documentos emitidos.</div>}
        {docs.map((d) => (
          <button key={d.id} onClick={() => api.tributario.documento(d.id).then(setDetalle)} className="text-left rounded-2xl border border-border bg-white px-4 py-3 flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-[13.5px] font-semibold text-ink truncate">{tipoLabel(d.tipo_documento)} · #{d.folio}</div>
              <div className="text-[11px] text-sub truncate">{d.organo} · {fecha(d.emitido_at)}{d.receptor_nombre ? ` · ${d.receptor_nombre}` : ''}</div>
            </div>
            <div className="text-right shrink-0 pl-2">
              <div className="text-[13px] font-semibold text-ink tabular-nums">{fmt(d.total, d.moneda)}</div>
              <StatusTag label={d.estado} tone={estadoTone(d.estado)} />
            </div>
          </button>
        ))}
      </div>

      {/* Sheet: emisor */}
      {sheet === 'emisor' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Emisor fiscal</div>
          <div className="text-[12.5px] text-sub">Identidad del emisor ante {tipos?.pais === 'BR' ? 'la prefeitura / SEFAZ' : 'el SII'}.</div>
          <input value={em.tax_id} onChange={(e) => setEm((p) => ({ ...p, tax_id: e.target.value }))} placeholder={tipos?.pais === 'BR' ? 'CNPJ' : 'RUT (76.123.456-7)'}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={em.razon_social} onChange={(e) => setEm((p) => ({ ...p, razon_social: e.target.value }))} placeholder="Razón social"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={em.giro} onChange={(e) => setEm((p) => ({ ...p, giro: e.target.value }))} placeholder="Giro / atividade"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <input value={em.direccion} onChange={(e) => setEm((p) => ({ ...p, direccion: e.target.value }))} placeholder="Dirección"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={guardarEmisor} disabled={saving || !em.tax_id || !em.razon_social} className="w-full">{saving ? 'Guardando…' : 'Guardar'}</Button>
        </BottomSheet>
      )}

      {/* Sheet: emitir */}
      {sheet === 'emitir' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Emitir documento</div>
          <select value={form.tipo_documento} onChange={(e) => setForm((p) => ({ ...p, tipo_documento: e.target.value, serie: tipos?.pais === 'BR' ? (e.target.value === 'nfse' ? 'RPS' : '1') : '' }))}
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
            {(tipos?.tipos ?? []).map((t) => <option key={t} value={t}>{tipoLabel(t)}</option>)}
          </select>
          <input value={form.descripcion} onChange={(e) => setForm((p) => ({ ...p, descripcion: e.target.value }))} placeholder="Descripción del ítem (ej. Consulta)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <div className="flex gap-2">
            <input value={form.cantidad} onChange={(e) => setForm((p) => ({ ...p, cantidad: e.target.value }))} placeholder="Cant." inputMode="numeric"
              className="w-24 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={form.precio} onChange={(e) => setForm((p) => ({ ...p, precio: e.target.value }))} placeholder="Precio unitario" inputMode="numeric"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          <div className="flex gap-2">
            <input value={form.receptor_tax_id} onChange={(e) => setForm((p) => ({ ...p, receptor_tax_id: e.target.value }))} placeholder={tipos?.pais === 'BR' ? 'CPF/CNPJ receptor (opc.)' : 'RUT receptor (opc.)'}
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <input value={form.receptor_nombre} onChange={(e) => setForm((p) => ({ ...p, receptor_nombre: e.target.value }))} placeholder="Nombre (opc.)"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          </div>
          {form.tipo_documento === 'boleta_electronica' && <div className="text-[11px] text-sub">La boleta considera el precio con IVA incluido.</div>}
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={emitir} disabled={saving || !form.precio} className="w-full">{saving ? 'Emitiendo…' : 'Emitir'}</Button>
        </BottomSheet>
      )}

      {/* Sheet: detalle documento */}
      {detalle && (
        <BottomSheet onClose={() => setDetalle(null)}>
          <div className="flex items-center justify-between">
            <div className="font-heading font-extrabold text-[17px] text-ink">{tipoLabel(detalle.tipo_documento)} · #{detalle.folio}</div>
            <StatusTag label={detalle.estado} tone={estadoTone(detalle.estado)} />
          </div>
          <div className="text-[12.5px] text-sub">{detalle.organo} · {detalle.jurisdiccion} · {fecha(detalle.emitido_at)}</div>
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Neto</div><div className="font-bold text-ink tabular-nums text-[13px]">{fmt(detalle.neto, detalle.moneda)}</div></div>
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">{(detalle.impuesto_detalle?.tipo as string) ?? 'Impuesto'}</div><div className="font-bold text-ink tabular-nums text-[13px]">{fmt(detalle.impuesto, detalle.moneda)}</div></div>
            <div className="rounded-xl border border-border bg-white px-3 py-2"><div className="text-[11px] text-sub">Total</div><div className="font-bold text-teal-dark tabular-nums text-[13px]">{fmt(detalle.total, detalle.moneda)}</div></div>
          </div>
          {detalle.receptor_nombre && <div className="text-[12.5px] text-ink">Receptor: {detalle.receptor_nombre}{detalle.receptor_tax_id ? ` (${detalle.receptor_tax_id})` : ''}</div>}
          {detalle.track_id && <div className="text-[11px] text-sub break-all">{tipos?.pais === 'BR' ? 'Protocolo' : 'Track ID SII'}: {detalle.track_id}</div>}
          {detalle.sello && <div className="text-[11px] text-sub break-all">{tipos?.pais === 'BR' ? 'Código de verificação' : 'Timbre (TED)'}: {detalle.sello.slice(0, 44)}…</div>}
          {detalle.motivo && <div className="text-[12px] text-danger">Anulado: {detalle.motivo}</div>}
          {detalle.xml && (
            <details className="rounded-xl border border-border bg-[#FAFCFB] p-2">
              <summary className="text-[12px] font-semibold text-ink cursor-pointer">Ver XML del documento</summary>
              <pre className="mt-2 max-h-48 overflow-auto text-[10px] leading-snug text-sub whitespace-pre-wrap break-all">{detalle.xml}</pre>
            </details>
          )}
          {detalle.estado === 'aceptado' && (
            <Button onClick={() => anular(detalle.id)} variant="outline" className="w-full">
              {tipos?.pais === 'BR' ? 'Cancelar (cancelamento)' : 'Anular (nota de crédito)'}
            </Button>
          )}
          <Button onClick={() => setDetalle(null)} variant="ghost" className="w-full">Cerrar</Button>
        </BottomSheet>
      )}
    </div>
  );
}
