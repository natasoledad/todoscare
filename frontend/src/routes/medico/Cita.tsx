import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import { estadoCita, money } from '../../lib/citas';
import type { AlertaClinica, CitaMedico, FichaEsp, Prontuario, RecetaItem, RecetaPlantilla, Vademecum } from '../../api/types';

export function Cita() {
  const { citaId = '' } = useParams();
  const navigate = useNavigate();
  const [cita, setCita] = useState<CitaMedico | null>(null);
  const [prontuarios, setProntuarios] = useState<Prontuario[]>([]);

  // atención form
  const [motivo, setMotivo] = useState('');
  const [evolucion, setEvolucion] = useState('');
  const [diagnostico, setDiagnostico] = useState('');
  const [savingAtencion, setSavingAtencion] = useState(false);

  // prescripción form
  const [medicamento, setMedicamento] = useState('');
  const [cantidad, setCantidad] = useState('');
  const [indicaciones, setIndicaciones] = useState('');
  const [alertas, setAlertas] = useState<AlertaClinica[]>([]);
  const [prescribiendo, setPrescribiendo] = useState(false);
  const [prescripcionMsg, setPrescripcionMsg] = useState<string | null>(null);
  const [vademecum, setVademecum] = useState<Vademecum[]>([]);
  const [recetas, setRecetas] = useState<RecetaPlantilla[]>([]);

  useEffect(() => { api.medico.recetasPlantilla().then((r) => setRecetas(r.filter((x) => x.activo))).catch(() => setRecetas([])); }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      if (medicamento.trim().length < 2) { setVademecum([]); return; }
      api.medico.vademecum(medicamento.trim()).then(setVademecum).catch(() => setVademecum([]));
    }, 250);
    return () => clearTimeout(t);
  }, [medicamento]);

  const [ordenMsg, setOrdenMsg] = useState<string | null>(null);
  const [cierreMsg, setCierreMsg] = useState<string | null>(null);

  const load = async () => {
    const agenda = await api.medico.agenda();
    const found = agenda.find((c) => c.id === citaId) ?? null;
    setCita(found);
    setProntuarios(await api.medico.prontuario(citaId));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citaId]);

  const [atencionError, setAtencionError] = useState<string | null>(null);
  const [fichas, setFichas] = useState<FichaEsp[]>([]);
  const [fichaId, setFichaId] = useState('');
  const [extra, setExtra] = useState<Record<string, string>>({});

  useEffect(() => { api.medico.fichasEspecialidad().then((fs) => setFichas(fs.filter((f) => f.activo))).catch(() => setFichas([])); }, []);
  const ficha = fichas.find((f) => f.id === fichaId);

  const registrarAtencion = async () => {
    setSavingAtencion(true);
    setAtencionError(null);
    try {
      const contenido_extra: Record<string, unknown> = {};
      for (const c of ficha?.campos ?? []) {
        const v = extra[c.clave];
        if (v !== undefined && v !== '') contenido_extra[c.clave] = c.tipo === 'numero' ? Number(v) : c.tipo === 'checkbox' ? v === 'true' : v;
      }
      await api.medico.registrarAtencion(citaId, { motivo, evolucion, diagnostico, contenido_extra: Object.keys(contenido_extra).length ? contenido_extra : undefined });
      setMotivo('');
      setEvolucion('');
      setDiagnostico('');
      setExtra({});
      await load();
    } catch (e) {
      setAtencionError(e instanceof ApiError ? String(e.detail) : 'No se pudo guardar en el prontuario');
    } finally {
      setSavingAtencion(false);
    }
  };

  const prescribirItems = async (items: RecetaItem[], confirmar: boolean) => {
    setPrescribiendo(true);
    setPrescripcionMsg(null);
    try {
      const res = await api.medico.prescribir(citaId, items.map((i) => ({ medicamento: i.medicamento, cantidad: i.cantidad ?? undefined, indicaciones: i.indicaciones ?? undefined })), confirmar);
      if (!res.prescripcion) {
        setAlertas(res.alertas);
      } else {
        setAlertas([]);
        setPrescripcionMsg('✅ Prescripción firmada y enviada a farmacia');
        setMedicamento('');
        setCantidad('');
        setIndicaciones('');
      }
    } catch (e) {
      setPrescripcionMsg(e instanceof ApiError ? String(e.detail) : 'Error al prescribir');
    } finally {
      setPrescribiendo(false);
    }
  };

  const ordenar = async (tipo: 'laboratorio' | 'imagenes') => {
    await api.medico.ordenExamen(citaId, tipo);
    setOrdenMsg(`✅ Orden de ${tipo} creada y enviada a laboratorio`);
  };

  const cerrar = async () => {
    try {
      const res = await api.medico.cerrar(citaId);
      setCierreMsg(`✅ Atención cerrada. Liquidación: ${money(res.split_monto ?? 0)}`);
      await load();
    } catch (e) {
      setCierreMsg(e instanceof ApiError ? String(e.detail) : 'No se pudo cerrar la atención');
    }
  };

  const noShow = async () => {
    try {
      await api.medico.noShow(citaId);
      setCierreMsg('Cita marcada como "no asistió".');
      await load();
    } catch (e) {
      setCierreMsg(e instanceof ApiError ? String(e.detail) : 'No se pudo actualizar la cita');
    }
  };

  if (!cita) return <div className="h-full flex items-center justify-center text-sub text-sm">Cargando…</div>;

  const cerrada = ['completada', 'cancelada', 'no_show'].includes(cita.estado);

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Atención" onBack={() => navigate('/medico')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-8 flex flex-col gap-4">
        {/* patient header */}
        <div className="rounded-2xl bg-gradient-to-br from-teal to-teal-dark text-white p-4">
          <div className="font-heading font-extrabold text-lg">{cita.paciente_nombre}</div>
          <div className="text-[12.5px] opacity-85 mt-0.5">
            {cita.servicio_nombre} · {new Date(cita.inicio).toLocaleString('es-CL', { dateStyle: 'medium', timeStyle: 'short' })}
          </div>
          <button
            onClick={() => navigate(`/medico/ficha/${cita.patient_id}`)}
            className="mt-2.5 text-[12.5px] font-heading font-bold underline cursor-pointer"
          >
            Ver ficha clínica completa ›
          </button>
        </div>

        {/* prontuario existente */}
        {prontuarios.length > 0 && (
          <div className="flex flex-col gap-2">
            <div className="font-heading font-bold text-[13px] text-ink">Prontuario</div>
            {prontuarios.map((p) => (
              <div key={p.id} className="rounded-2xl border border-border bg-white p-3.5 text-[13px]">
                <div className="text-ink font-semibold">{String(p.contenido.motivo ?? 'Registro')}</div>
                {!!p.contenido.diagnostico && <div className="text-sub mt-1">Dx: {String(p.contenido.diagnostico)}</div>}
                {!!p.contenido.enmiendas?.length && (
                  <div className="mt-1.5 text-[11.5px] text-warn">
                    {p.contenido.enmiendas.length} enmienda(s) registrada(s)
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!cerrada && (
          <>
            {/* registrar atención */}
            <div className="flex flex-col gap-2">
              <div className="font-heading font-bold text-[13px] text-ink">Registrar atención</div>
              <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo de consulta"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <textarea value={evolucion} onChange={(e) => setEvolucion(e.target.value)} placeholder="Evolución" rows={2}
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal resize-none" />
              <input value={diagnostico} onChange={(e) => setDiagnostico(e.target.value)} placeholder="Diagnóstico"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />

              {fichas.length > 0 && (
                <select value={fichaId} onChange={(e) => { setFichaId(e.target.value); setExtra({}); }}
                  className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
                  <option value="">Ficha por especialidad (opcional)…</option>
                  {fichas.map((f) => <option key={f.id} value={f.id}>{f.nombre}</option>)}
                </select>
              )}
              {ficha?.campos.map((c) => (
                <div key={c.clave}>
                  <div className="text-[11px] text-sub mb-0.5">{c.label}</div>
                  {c.tipo === 'area' ? (
                    <textarea value={extra[c.clave] ?? ''} onChange={(e) => setExtra((p) => ({ ...p, [c.clave]: e.target.value }))} rows={2}
                      className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal resize-none" />
                  ) : c.tipo === 'opcion' ? (
                    <select value={extra[c.clave] ?? ''} onChange={(e) => setExtra((p) => ({ ...p, [c.clave]: e.target.value }))}
                      className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
                      <option value="">—</option>{(c.opciones ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : c.tipo === 'checkbox' ? (
                    <label className="flex items-center gap-2"><input type="checkbox" checked={extra[c.clave] === 'true'} onChange={(e) => setExtra((p) => ({ ...p, [c.clave]: String(e.target.checked) }))} className="w-4 h-4 accent-teal" /><span className="text-[13px] text-ink">Sí</span></label>
                  ) : (
                    <input value={extra[c.clave] ?? ''} onChange={(e) => setExtra((p) => ({ ...p, [c.clave]: e.target.value }))} inputMode={c.tipo === 'numero' ? 'decimal' : 'text'}
                      className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-2.5 text-sm text-ink outline-none focus:border-teal" />
                  )}
                </div>
              ))}
              {atencionError && <div className="text-xs text-danger">{atencionError}</div>}
              <Button onClick={registrarAtencion} disabled={!motivo || savingAtencion} className="w-full">
                {savingAtencion ? 'Guardando…' : 'Guardar en prontuario'}
              </Button>
            </div>

            {/* prescripción */}
            <div className="flex flex-col gap-2">
              <div className="font-heading font-bold text-[13px] text-ink">Prescripción</div>
              {alertas.length > 0 && (
                <div className="rounded-2xl bg-[#FBECEA] border border-[#E8C5C0] p-3.5 text-[12.5px] text-[#9A342A]">
                  ⚠️ Alerta clínica: {alertas.map((a) => a.detalle).join('; ')}
                </div>
              )}
              {recetas.length > 0 && (
                <select value="" onChange={(e) => { const r = recetas.find((x) => x.id === e.target.value); if (r) prescribirItems(r.items, false); }}
                  className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3 py-2.5 text-sm text-ink outline-none focus:border-teal">
                  <option value="">Aplicar receta guardada…</option>
                  {recetas.map((r) => <option key={r.id} value={r.id}>{r.nombre} ({r.items.length})</option>)}
                </select>
              )}
              <input value={medicamento} onChange={(e) => setMedicamento(e.target.value)} placeholder="Medicamento (busca en el vademécum)" list="vademecum-list"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <datalist id="vademecum-list">
                {vademecum.map((m) => <option key={m.id} value={`${m.nombre}${m.presentacion ? ' ' + m.presentacion : ''}`} />)}
              </datalist>
              <div className="flex gap-2">
                <input value={cantidad} onChange={(e) => setCantidad(e.target.value)} placeholder="Cantidad"
                  className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
                <input value={indicaciones} onChange={(e) => setIndicaciones(e.target.value)} placeholder="Indicaciones"
                  className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              </div>
              {alertas.length > 0 ? (
                <Button onClick={() => prescribirItems([{ medicamento, cantidad, indicaciones }], true)} disabled={prescribiendo} variant="outline" className="w-full">
                  Firmar de todas formas
                </Button>
              ) : (
                <Button onClick={() => prescribirItems([{ medicamento, cantidad, indicaciones }], false)} disabled={!medicamento || prescribiendo} className="w-full">
                  {prescribiendo ? 'Firmando…' : 'Emitir y firmar'}
                </Button>
              )}
              {prescripcionMsg && <div className="text-[12.5px] text-teal-dark">{prescripcionMsg}</div>}
            </div>

            {/* orden de examen */}
            <div className="flex flex-col gap-2">
              <div className="font-heading font-bold text-[13px] text-ink">Orden de examen</div>
              <div className="flex gap-2">
                <Button onClick={() => ordenar('laboratorio')} variant="ghost" className="flex-1 text-[13px] py-3">🧪 Laboratorio</Button>
                <Button onClick={() => ordenar('imagenes')} variant="ghost" className="flex-1 text-[13px] py-3">🩻 Imágenes</Button>
              </div>
              {ordenMsg && <div className="text-[12.5px] text-teal-dark">{ordenMsg}</div>}
            </div>

            {/* cierre */}
            <div className="flex flex-col gap-2 pt-1">
              <Button onClick={cerrar} className="w-full">Cerrar atención</Button>
              <Button onClick={noShow} variant="outline" className="w-full">Marcar "no asistió"</Button>
            </div>
          </>
        )}

        {cierreMsg && <div className="rounded-2xl bg-teal-soft border border-[#CDEEE1] p-3.5 text-[13px] text-teal-dark font-semibold text-center">{cierreMsg}</div>}
        {cerrada && !cierreMsg && (
          <div className="rounded-2xl bg-[#F2F6F5] p-3.5 text-[13px] text-sub text-center">Esta cita está {estadoCita(cita.estado).label.toLowerCase()}.</div>
        )}
      </div>
    </div>
  );
}
