import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { Examen } from '../../api/types';

export function Subir() {
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
      <BackHeader title="Subir a tu ficha clínica" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        <div className="text-[13px] leading-relaxed text-sub">
          Sube una imagen o PDF de tus exámenes, ficha clínica u otra información. La IA la revisa y actualiza tu
          ficha.
        </div>

        <input
          ref={fileInput}
          type="file"
          accept="image/*,.pdf"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
        />
        <div
          onClick={() => !uploading && fileInput.current?.click()}
          className="rounded-2xl border-[1.5px] border-dashed border-[#B9D4CE] text-center text-teal-dark font-heading font-bold text-sm py-5 cursor-pointer"
        >
          {uploading ? 'Subiendo…' : '📎 Subir imagen o PDF'}
        </div>
        <div className="rounded-2xl border-[1.5px] border-dashed border-[#B9D4CE] text-center text-teal-dark font-heading font-bold text-sm py-5">
          💬 Enviar por WhatsApp al asistente
        </div>

        {examenes.map((ex) => (
          <div key={ex.id} className="flex items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3.5">
            <div className="w-10 h-10 rounded-[10px] bg-[#F2F6F5] flex items-center justify-center text-lg shrink-0">🤖</div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-ink truncate">{ex.nombre}</div>
              <div className="mt-0.5 text-xs text-sub">Agregado a tu ficha</div>
            </div>
            <span className="text-teal text-base">✓</span>
          </div>
        ))}
      </div>
    </div>
  );
}
