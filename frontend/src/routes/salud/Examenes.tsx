import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { StatusTag } from '../../components/ListRow';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { Examen } from '../../api/types';

export function Examenes() {
  const navigate = useNavigate();
  const { refreshMe } = useAuth();
  const [examenes, setExamenes] = useState<Examen[]>([]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = () => api.salud.examenes().then(setExamenes);

  useEffect(() => {
    load();
  }, []);

  const onFile = async (file: File) => {
    setUploading(true);
    await api.salud.subirExamen(file);
    await load();
    await refreshMe();
    setUploading(false);
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Resultados de exámenes" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-2.5">
        {examenes.length === 0 && <div className="text-center text-sm text-sub py-6">Aún no tienes exámenes.</div>}
        {examenes.map((ex) => (
          <div key={ex.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">🧪</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink truncate">{ex.nombre}</div>
              <div className="mt-0.5 text-xs text-sub">{new Date(ex.fecha).toLocaleDateString('es-MX')}</div>
            </div>
            <StatusTag label={ex.estado === 'listo' ? 'Listo' : ex.estado === 'en_proceso' ? 'En proceso' : ex.estado} tone={ex.estado === 'listo' ? 'teal' : 'warn'} />
          </div>
        ))}

        <input
          ref={fileInput}
          type="file"
          accept="image/*,.pdf"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <div
          onClick={() => !uploading && fileInput.current?.click()}
          className="mt-1.5 rounded-2xl border-[1.5px] border-dashed border-[#B9D4CE] text-center text-teal-dark font-heading font-bold text-sm py-4 cursor-pointer"
        >
          {uploading ? 'Subiendo…' : '📎 Subir examen (imagen o PDF)'}
        </div>
      </div>
    </div>
  );
}
