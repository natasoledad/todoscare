import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { FragmentoConocimiento, FuenteConocimiento } from '../../api/types';

const fecha = (iso: string) => new Date(iso).toLocaleDateString('es-CL', { day: '2-digit', month: 'short', year: '2-digit' });

export function Conocimiento() {
  const navigate = useNavigate();
  const [fuentes, setFuentes] = useState<FuenteConocimiento[]>([]);
  const [sheet, setSheet] = useState<null | 'texto' | 'buscar'>(null);
  const [nombre, setNombre] = useState('');
  const [texto, setTexto] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [consulta, setConsulta] = useState('');
  const [hits, setHits] = useState<FragmentoConocimiento[]>([]);

  const load = () => api.empresa.conocimiento().then(setFuentes).catch(() => setFuentes([]));
  useEffect(() => { load(); }, []);

  const subirTexto = async () => {
    setBusy(true); setError(null);
    try { await api.empresa.subirTextoConocimiento({ nombre, texto }); setNombre(''); setTexto(''); setSheet(null); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.'); }
    finally { setBusy(false); }
  };
  const subirPdf = async (file: File) => {
    setBusy(true); setError(null);
    try { await api.empresa.subirPdfConocimiento(file); await load(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo procesar el PDF.'); }
    finally { setBusy(false); }
  };
  const toggle = async (f: FuenteConocimiento) => { await api.empresa.editarFuenteConocimiento(f.id, { activo: !f.activo }); await load(); };
  const borrar = async (id: string) => { await api.empresa.eliminarFuenteConocimiento(id); await load(); };
  const buscar = async () => {
    if (!consulta.trim()) return;
    setBusy(true);
    try { const r = await api.empresa.buscarConocimiento(consulta.trim()); setHits(r.resultados); }
    finally { setBusy(false); }
  };

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Base de conocimiento IA" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-28 flex flex-col gap-2.5">
        <div className="text-[12px] text-sub">
          Sube PDFs o textos (protocolos, precios, indicaciones, preguntas frecuentes). La IA los usará como fuente al conversar con los pacientes. Todo queda dentro de tu plataforma.
        </div>
        {error && <div className="text-xs text-danger">{error}</div>}

        <div className="flex gap-2 flex-wrap">
          <button onClick={() => { setSheet('texto'); setError(null); }} className="rounded-full bg-teal text-white px-3 py-1.5 text-[12px] font-semibold">+ Texto</button>
          <label className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink cursor-pointer">
            + Subir PDF
            <input type="file" accept="application/pdf,.pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) subirPdf(f); }} />
          </label>
          <button onClick={() => { setSheet('buscar'); setHits([]); setConsulta(''); }} className="rounded-full border border-border bg-white px-3 py-1.5 text-[12px] font-semibold text-ink">Probar búsqueda</button>
        </div>

        {busy && <div className="text-[12px] text-sub">Procesando…</div>}
        {fuentes.length === 0 && !busy && <div className="text-sm text-sub">Aún no hay fuentes cargadas.</div>}
        {fuentes.map((f) => (
          <div key={f.id} className="rounded-2xl border border-border bg-white px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-lg">{f.tipo === 'pdf' ? '📄' : '📝'}</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-[13.5px] text-ink truncate">{f.nombre}</div>
                <div className="text-[11px] text-sub">{f.n_chunks} fragmento(s) · {fecha(f.fecha)}{f.estado === 'error' ? ' · error' : ''}</div>
              </div>
              <button onClick={() => toggle(f)} className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${f.activo ? 'bg-teal-soft text-teal-dark' : 'bg-[#F1F1F1] text-sub'}`}>{f.activo ? 'Activa' : 'Inactiva'}</button>
              <button onClick={() => borrar(f.id)} className="text-[11px] font-semibold text-danger">Borrar</button>
            </div>
          </div>
        ))}
      </div>

      {sheet === 'texto' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Agregar texto</div>
          <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Título (p. ej. Preguntas frecuentes)"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          <textarea value={texto} onChange={(e) => setTexto(e.target.value)} rows={8} placeholder="Pega aquí el contenido que la IA debe conocer…"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={subirTexto} disabled={busy || !nombre || !texto} className="w-full">{busy ? 'Guardando…' : 'Guardar en la base'}</Button>
        </BottomSheet>
      )}

      {sheet === 'buscar' && (
        <BottomSheet onClose={() => setSheet(null)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Probar búsqueda</div>
          <div className="text-[12px] text-sub">Escribe una pregunta y mira qué fragmentos recuperaría la IA.</div>
          <div className="flex gap-2">
            <input value={consulta} onChange={(e) => setConsulta(e.target.value)} placeholder="¿Cuánto dura una limpieza?"
              className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
            <Button onClick={buscar} disabled={busy || !consulta.trim()} className="shrink-0">Buscar</Button>
          </div>
          <div className="flex flex-col gap-2 max-h-[45vh] overflow-y-auto scrollhide">
            {hits.length === 0 && <div className="text-[12px] text-sub">Sin resultados todavía.</div>}
            {hits.map((h, i) => (
              <div key={i} className="rounded-xl bg-[#F6FBF9] px-3 py-2.5">
                <div className="text-[10.5px] text-teal-dark font-semibold">{h.fuente} · {(h.score * 100).toFixed(0)}%</div>
                <div className="text-[12.5px] text-ink mt-0.5">{h.texto}</div>
              </div>
            ))}
          </div>
        </BottomSheet>
      )}
    </div>
  );
}
