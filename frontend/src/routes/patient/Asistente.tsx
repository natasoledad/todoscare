import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { BackHeader } from '../../components/BackHeader';
import { api, ApiError } from '../../api/client';

interface Msg { de: 'bot' | 'yo'; texto: string; }

const SUGERENCIAS = ['¿Cuándo es mi próxima cita?', '¿Cómo agendo?', 'Ver mi ficha', 'Mis recetas'];

export function Asistente() {
  const navigate = useNavigate();
  const [msgs, setMsgs] = useState<Msg[]>([
    { de: 'bot', texto: '¡Hola! Soy el asistente de TODOSCARE 💬 Puedo contarte tu próxima cita, ayudarte a agendar o mostrarte tu ficha. ¿Qué necesitas?' },
  ]);
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs, enviando]);

  const enviar = async (t: string) => {
    const q = t.trim();
    if (!q || enviando) return;
    setMsgs((m) => [...m, { de: 'yo', texto: q }]);
    setTexto('');
    setEnviando(true);
    try {
      const r = await api.integraciones.whatsapp(q);
      setMsgs((m) => [...m, { de: 'bot', texto: r.reply }]);
    } catch (e) {
      setMsgs((m) => [...m, { de: 'bot', texto: e instanceof ApiError ? String(e.detail) : 'No pude responder ahora.' }]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="Asistente por WhatsApp" onBack={() => navigate('/app')} />
      <div className="flex-1 overflow-y-auto scrollhide px-4 pt-3 pb-3 flex flex-col gap-2.5" style={{ background: '#E9F5EF' }}>
        {msgs.map((m, i) => (
          <div key={i} className={`max-w-[82%] px-3.5 py-2.5 text-[13.5px] leading-snug rounded-2xl ${m.de === 'yo' ? 'self-end bg-teal text-white rounded-br-md' : 'self-start bg-white text-ink rounded-bl-md border border-border'}`}>
            {m.texto}
          </div>
        ))}
        {enviando && <div className="self-start bg-white text-sub text-[13px] px-3.5 py-2.5 rounded-2xl rounded-bl-md border border-border">escribiendo…</div>}
        <div ref={endRef} />
      </div>

      <div className="px-4 pt-2 flex gap-2 overflow-x-auto scrollhide">
        {SUGERENCIAS.map((s) => (
          <button key={s} onClick={() => enviar(s)} disabled={enviando} className="whitespace-nowrap text-[12px] font-semibold text-teal-dark bg-teal-soft border border-[#CDEEE1] rounded-full px-3 py-1.5">
            {s}
          </button>
        ))}
      </div>
      <div className="px-4 py-3 flex gap-2 items-center">
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') enviar(texto); }}
          placeholder="Escribe un mensaje…"
          className="flex-1 rounded-full border-[1.5px] border-border-strong bg-white px-4 py-2.5 text-sm text-ink outline-none focus:border-teal"
        />
        <button onClick={() => enviar(texto)} disabled={enviando || !texto.trim()} className="w-11 h-11 rounded-full bg-teal text-white text-lg shrink-0 disabled:opacity-45">↑</button>
      </div>
    </div>
  );
}
