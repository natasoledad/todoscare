import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api, ApiError } from '../../api/client';
import type { AlertaClinica, CitaMedico, Prontuario } from '../../api/types';

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

  const registrarAtencion = async () => {
    setSavingAtencion(true);
    await api.medico.registrarAtencion(citaId, { motivo, evolucion, diagnostico });
    setMotivo('');
    setEvolucion('');
    setDiagnostico('');
    await load();
    setSavingAtencion(false);
  };

  const prescribir = async (confirmar: boolean) => {
    setPrescribiendo(true);
    setPrescripcionMsg(null);
    try {
      const res = await api.medico.prescribir(citaId, [{ medicamento, cantidad, indicaciones }], confirmar);
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
    const res = await api.medico.cerrar(citaId);
    setCierreMsg(`✅ Atención cerrada. Liquidación: $${res.split_monto ?? 0}`);
    await load();
  };

  const noShow = async () => {
    await api.medico.noShow(citaId);
    setCierreMsg('Cita marcada como "no asistió".');
    await load();
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
            {cita.servicio_nombre} · {new Date(cita.inicio).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })}
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
              <input value={medicamento} onChange={(e) => setMedicamento(e.target.value)} placeholder="Medicamento"
                className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              <div className="flex gap-2">
                <input value={cantidad} onChange={(e) => setCantidad(e.target.value)} placeholder="Cantidad"
                  className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
                <input value={indicaciones} onChange={(e) => setIndicaciones(e.target.value)} placeholder="Indicaciones"
                  className="flex-1 rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
              </div>
              {alertas.length > 0 ? (
                <Button onClick={() => prescribir(true)} disabled={prescribiendo} variant="outline" className="w-full">
                  Firmar de todas formas
                </Button>
              ) : (
                <Button onClick={() => prescribir(false)} disabled={!medicamento || prescribiendo} className="w-full">
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
          <div className="rounded-2xl bg-[#F2F6F5] p-3.5 text-[13px] text-sub text-center">Esta cita está {cita.estado}.</div>
        )}
      </div>
    </div>
  );
}
