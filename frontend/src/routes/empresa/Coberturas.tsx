import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { api, ApiError } from '../../api/client';
import type { CalculoCopago, CoberturaCopago } from '../../api/types';

const TIPO_LABEL: Record<string, string> = {
  seguro_complementario: 'Seguro complementario',
  caja_compensacion: 'Caja de compensación (CCAF)',
};
const clp = (n: number) => `$${Math.round(n).toLocaleString('es-CL')}`;

export function Coberturas() {
  const navigate = useNavigate();
  const [coberturas, setCoberturas] = useState<CoberturaCopago[]>([]);
  const [edit, setEdit] = useState<CoberturaCopago | 'nueva' | null>(null);

  const load = () => api.copago.coberturas().then(setCoberturas);
  useEffect(() => { load(); }, []);

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Coberturas de copago" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-28 flex flex-col gap-2.5">
        <div className="text-[12px] text-sub">
          En Chile el copago no termina en el bono Fonasa/Isapre: los <b>seguros complementarios</b> y las
          <b> cajas de compensación</b> bonifican lo que finalmente paga el paciente. Definí acá cada capa y usá
          la calculadora para ver el copago final.
        </div>

        <Calculadora coberturas={coberturas.filter((c) => c.activo)} />

        <div className="font-heading font-bold text-[13px] text-ink pt-2">Capas configuradas</div>
        {coberturas.length === 0 && <div className="text-xs text-sub">Aún no hay coberturas. Agregá la primera.</div>}
        {coberturas.map((c) => (
          <div key={c.id} className="rounded-2xl border border-border bg-white px-4 py-3" onClick={() => setEdit(c)}>
            <div className="flex items-center gap-2">
              <div className="font-semibold text-sm text-ink">{c.nombre}</div>
              {!c.activo && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#F1F1F1] text-sub">inactiva</span>}
              {c.permite_cuotas && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-teal-soft text-teal-dark">cuotas</span>}
            </div>
            <div className="mt-0.5 text-xs text-sub">{TIPO_LABEL[c.tipo] ?? c.tipo}</div>
            <div className="mt-1 text-[11.5px] text-teal-dark">
              {c.modalidad === 'porcentaje' ? `Bonifica ${Math.round(c.valor * 100)}% del copago` : `Aporte fijo ${clp(c.valor)}`}
              {c.tope != null && ` · tope ${clp(c.tope)}`}
              {c.deducible != null && ` · deducible ${clp(c.deducible)}`}
            </div>
          </div>
        ))}
      </div>

      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setEdit('nueva')} className="w-full">+ Nueva cobertura</Button>
      </div>

      {edit && (
        <CoberturaEditor
          cobertura={edit === 'nueva' ? null : edit}
          onClose={() => setEdit(null)}
          onSaved={() => { setEdit(null); load(); }}
        />
      )}
    </div>
  );
}

function Calculadora({ coberturas }: { coberturas: CoberturaCopago[] }) {
  const [precio, setPrecio] = useState('');
  const [prevPct, setPrevPct] = useState('70');
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [res, setRes] = useState<CalculoCopago | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggle = (id: string) => setSel((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const calcular = async () => {
    setError(null); setRes(null);
    const p = Number(precio);
    if (!p || p <= 0) { setError('Ingresá el precio de la prestación.'); return; }
    try {
      const r = await api.copago.calcular({ precio: p, prevision_pct: Number(prevPct) / 100, cobertura_ids: [...sel] });
      setRes(r);
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo calcular.');
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-white px-4 py-3.5 flex flex-col gap-2.5">
      <div className="font-heading font-bold text-[13px] text-ink">Calculadora de copago</div>
      <div className="flex gap-2">
        <div className="flex-1">
          <label className="text-[11px] text-sub">Precio prestación</label>
          <input inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value.replace(/\D/g, ''))} placeholder="50000"
            className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal" />
        </div>
        <div className="w-28">
          <label className="text-[11px] text-sub">Bono previsión %</label>
          <input inputMode="numeric" value={prevPct} onChange={(e) => setPrevPct(e.target.value.replace(/\D/g, ''))}
            className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal" />
        </div>
      </div>
      {coberturas.length > 0 && (
        <div className="flex flex-col gap-1">
          <div className="text-[11px] text-sub">Capas complementarias</div>
          {coberturas.map((c) => (
            <label key={c.id} className="flex items-center gap-2 text-[12.5px] text-ink">
              <input type="checkbox" checked={sel.has(c.id)} onChange={() => toggle(c.id)} className="w-4 h-4 accent-teal" />
              {c.nombre}
            </label>
          ))}
        </div>
      )}
      <Button onClick={calcular} variant="outline" className="w-full">Calcular copago</Button>
      {error && <div className="text-xs text-danger">{error}</div>}
      {res && (
        <div className="rounded-xl bg-[#F6FBF9] px-3 py-2.5 text-[12.5px] text-ink flex flex-col gap-1">
          {res.aportes.map((a, i) => (
            <div key={i} className="flex justify-between text-sub"><span>− {a.nombre}</span><span className="tabular-nums">{clp(a.aporte)}</span></div>
          ))}
          <div className="flex justify-between font-heading font-extrabold text-ink border-t border-border pt-1 mt-0.5">
            <span>Copago final</span><span className="tabular-nums">{clp(res.copago_final)}</span>
          </div>
          {res.permite_cuotas && <div className="text-[11px] text-teal-dark">Financiable en cuotas (caja de compensación).</div>}
        </div>
      )}
    </div>
  );
}

function CoberturaEditor({ cobertura, onClose, onSaved }: {
  cobertura: CoberturaCopago | null; onClose: () => void; onSaved: () => void;
}) {
  const esNueva = cobertura === null;
  const [tipo, setTipo] = useState(cobertura?.tipo ?? 'seguro_complementario');
  const [nombre, setNombre] = useState(cobertura?.nombre ?? '');
  const [modalidad, setModalidad] = useState(cobertura?.modalidad ?? 'porcentaje');
  const [valor, setValor] = useState(
    cobertura ? (cobertura.modalidad === 'porcentaje' ? String(Math.round(cobertura.valor * 100)) : String(cobertura.valor)) : '',
  );
  const [tope, setTope] = useState(cobertura?.tope != null ? String(cobertura.tope) : '');
  const [deducible, setDeducible] = useState(cobertura?.deducible != null ? String(cobertura.deducible) : '');
  const [cuotas, setCuotas] = useState(cobertura?.permite_cuotas ?? false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const guardar = async () => {
    setSaving(true); setError(null);
    // En porcentaje el usuario escribe 0..100; el backend espera fracción 0..1.
    const valorNum = modalidad === 'porcentaje' ? Number(valor) / 100 : Number(valor);
    const body = {
      nombre, modalidad, valor: valorNum,
      tope: tope ? Number(tope) : null,
      deducible: deducible ? Number(deducible) : null,
      permite_cuotas: cuotas,
    };
    try {
      if (esNueva) await api.copago.crearCobertura({ tipo, ...body });
      else await api.copago.editarCobertura(cobertura!.id, body);
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar.');
      setSaving(false);
    }
  };

  const eliminar = async () => {
    if (!cobertura) return;
    setSaving(true); setError(null);
    try { await api.copago.eliminarCobertura(cobertura.id); onSaved(); }
    catch (e) { setError(e instanceof ApiError ? String(e.detail) : 'No se pudo eliminar.'); setSaving(false); }
  };

  return (
    <BottomSheet onClose={onClose}>
      <div className="font-heading font-extrabold text-[17px] text-ink">{esNueva ? 'Nueva cobertura' : `Editar · ${cobertura?.nombre}`}</div>

      <select value={tipo} onChange={(e) => setTipo(e.target.value)} disabled={!esNueva}
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal disabled:opacity-60">
        <option value="seguro_complementario">Seguro complementario</option>
        <option value="caja_compensacion">Caja de compensación (CCAF)</option>
      </select>

      <input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (p. ej. Consorcio Salud, CCAF Los Andes)"
        className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />

      <div className="flex gap-2">
        <select value={modalidad} onChange={(e) => setModalidad(e.target.value)}
          className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal">
          <option value="porcentaje">% del copago</option>
          <option value="monto">Monto fijo</option>
        </select>
        <input inputMode="numeric" value={valor} onChange={(e) => setValor(e.target.value.replace(/\D/g, ''))}
          placeholder={modalidad === 'porcentaje' ? '50 (%)' : '3000 (CLP)'}
          className="w-32 rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-3 text-sm text-ink outline-none focus:border-teal" />
      </div>

      <div className="flex gap-2">
        <div className="flex-1">
          <label className="text-[11px] text-sub">Tope aporte (opcional)</label>
          <input inputMode="numeric" value={tope} onChange={(e) => setTope(e.target.value.replace(/\D/g, ''))} placeholder="CLP"
            className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal" />
        </div>
        <div className="flex-1">
          <label className="text-[11px] text-sub">Deducible (opcional)</label>
          <input inputMode="numeric" value={deducible} onChange={(e) => setDeducible(e.target.value.replace(/\D/g, ''))} placeholder="CLP"
            className="mt-1 w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal" />
        </div>
      </div>

      <label className="flex items-center gap-2.5 py-1">
        <input type="checkbox" checked={cuotas} onChange={(e) => setCuotas(e.target.checked)} className="w-4 h-4 accent-teal" />
        <span className="text-[13px] text-ink">Permite financiar el copago en cuotas</span>
      </label>

      {error && <div className="text-xs text-danger">{error}</div>}
      <Button onClick={guardar} disabled={saving || !nombre || !valor} className="w-full">
        {saving ? 'Guardando…' : esNueva ? 'Crear cobertura' : 'Guardar cambios'}
      </Button>
      {!esNueva && (
        <button onClick={eliminar} disabled={saving} className="w-full text-[12.5px] font-semibold text-danger py-1.5">Eliminar cobertura</button>
      )}
    </BottomSheet>
  );
}
