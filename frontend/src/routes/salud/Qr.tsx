import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import QRCode from 'qrcode';
import { BackHeader } from '../../components/BackHeader';
import { Button } from '../../components/Button';
import { api } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type { EmergencyQr, QrAccessLog } from '../../api/types';

export function Qr() {
  const navigate = useNavigate();
  const { patient } = useAuth();
  const [qr, setQr] = useState<EmergencyQr | null>(null);
  const [accesos, setAccesos] = useState<QrAccessLog[]>([]);
  const [imgSrc, setImgSrc] = useState<string>('');

  useEffect(() => {
    (async () => {
      const q = await api.salud.qr();
      setQr(q);
      const url = `${window.location.origin}/qr/${q.token}`;
      setImgSrc(await QRCode.toDataURL(url, { margin: 1, width: 260, color: { dark: '#0F2A24', light: '#FFFFFF' } }));
      setAccesos(await api.salud.qrAccesos());
    })();
  }, []);

  if (!qr) return null;

  return (
    <div className="h-full flex flex-col">
      <BackHeader title="QR de emergencia" onBack={() => navigate('/app/salud')} />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-4 pb-6 flex flex-col gap-3">
        <div className="text-[13px] leading-relaxed text-sub">
          En un accidente o urgencia, el médico que te atienda escanea este código y accede a tu ficha clínica,
          historial y resultados de exámenes — sin necesitar tu clave.
        </div>
        <div className="bg-white border border-border rounded-[20px] p-6 flex flex-col items-center gap-3.5">
          {imgSrc && <img src={imgSrc} alt="QR de emergencia" className="w-[180px] h-[180px]" />}
          <div className="font-bold text-[13px] text-ink text-center">
            {patient?.nombre} {qr.resumen.grupo_sanguineo ? `· ${qr.resumen.grupo_sanguineo}` : ''}
            {qr.resumen.alergias ? ` · Alergia: ${qr.resumen.alergias}` : ''}
          </div>
          <div className="text-[11.5px] text-sub text-center">Acceso de solo lectura · válido con verificación médica</div>
        </div>
        <Button className="w-full">Compartir / imprimir QR</Button>
        <Button variant="ghost" className="w-full">
          Agregar a la pantalla de bloqueo
        </Button>
        <div className="rounded-2xl bg-warn-bg border border-warn-border p-3.5 text-xs leading-relaxed text-[#8A6A00]">
          🔒 Cada acceso queda registrado con fecha, hora y profesional que consultó.
        </div>

        {accesos.length > 0 && (
          <>
            <div className="font-heading font-bold text-[13px] text-ink pt-2">Accesos registrados</div>
            {accesos.map((a, i) => (
              <div key={i} className="flex justify-between rounded-2xl border border-border bg-white px-4 py-3 text-[13px]">
                <span className="text-ink font-medium">{a.profesional_nombre || 'Profesional'}</span>
                <span className="text-sub">{new Date(a.fecha).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
