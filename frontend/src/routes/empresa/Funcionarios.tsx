import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { BottomSheet } from '../../components/BottomSheet';
import { StatusTag } from '../../components/ListRow';
import { api, ApiError } from '../../api/client';
import type { Funcionario } from '../../api/types';

export function Funcionarios() {
  const navigate = useNavigate();
  const [funcionarios, setFuncionarios] = useState<Funcionario[]>([]);
  const [open, setOpen] = useState(false);
  const [correo, setCorreo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const load = () => api.empresa.funcionarios().then(setFuncionarios);
  useEffect(() => { load(); }, []);

  const alta = async () => {
    setError(null);
    setSaving(true);
    try {
      await api.empresa.altaFuncionario(correo);
      setCorreo('');
      setOpen(false);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? String(e.detail) : 'No se pudo dar de alta');
    } finally {
      setSaving(false);
    }
  };

  const baja = async (id: string) => {
    await api.empresa.bajaFuncionario(id);
    await load();
  };

  const activos = funcionarios.filter((f) => f.estado === 'activo');

  return (
    <div className="h-full flex flex-col relative">
      <BackHeader title="Funcionarios (B2B)" onBack={() => navigate('/empresa')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-3 pb-24 flex flex-col gap-2.5">
        <div className="text-[12.5px] text-sub">Nómina cubierta por el plan corporativo. Da de alta pacientes por su correo.</div>
        {funcionarios.length === 0 && <div className="text-center text-sm text-sub py-8">Aún no hay funcionarios.</div>}
        {funcionarios.map((f) => (
          <div key={f.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-11 h-11 rounded-xl bg-teal-soft flex items-center justify-center text-lg shrink-0">🧑‍💼</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink">{f.nombre}</div>
              <div className="mt-0.5 text-xs text-sub truncate">{f.correo}</div>
            </div>
            {f.estado === 'activo' ? (
              <div onClick={() => baja(f.id)} className="cursor-pointer text-[13px] font-bold text-danger">Baja</div>
            ) : (
              <StatusTag label="Baja" tone="warn" />
            )}
          </div>
        ))}
      </div>
      <div className="absolute left-0 right-0 bottom-0 px-5 pb-6 pt-3 bg-gradient-to-t from-bg via-bg to-transparent">
        <Button onClick={() => setOpen(true)} className="w-full">+ Alta de funcionario ({activos.length} activos)</Button>
      </div>

      {open && (
        <BottomSheet onClose={() => setOpen(false)}>
          <div className="font-heading font-extrabold text-[17px] text-ink">Alta de funcionario</div>
          <div className="text-[12.5px] text-sub">Debe ser un paciente ya registrado en la clínica.</div>
          <input value={correo} onChange={(e) => setCorreo(e.target.value)} placeholder="correo@ejemplo.com"
            className="w-full rounded-xl border-[1.5px] border-border-strong bg-white px-3.5 py-3 text-sm text-ink outline-none focus:border-teal" />
          {error && <div className="text-xs text-danger">{error}</div>}
          <Button onClick={alta} disabled={!correo || saving} className="w-full">
            {saving ? 'Dando de alta…' : 'Dar de alta'}
          </Button>
        </BottomSheet>
      )}
    </div>
  );
}
