import { useNavigate } from 'react-router-dom';
import { ScreenHeader } from '../../components/ScreenHeader';
import { ListRow, Chevron } from '../../components/ListRow';

const MENU = [
  { id: 'ficha', icon: '📋', t: 'Mi ficha clínica', d: 'Datos médicos, alergias, antecedentes' },
  { id: 'examenes', icon: '🧪', t: 'Resultados de exámenes realizados', d: 'Laboratorio, imágenes y odontograma' },
  { id: 'qr', icon: '🆘', t: 'QR de emergencia', d: 'Acceso médico a tu ficha en urgencias' },
  { id: 'dental', icon: '🦷', t: 'Ficha dental', d: 'Odontograma y tratamientos' },
  { id: 'agendamientos', icon: '📅', t: 'Agendamientos realizados', d: 'Historial de consultas y citas' },
  { id: 'hospitalizaciones', icon: '🏥', t: 'Hospitalizaciones realizadas', d: 'Ingresos y cirugías' },
  { id: 'subir', icon: '📎', t: 'Subir info a tu ficha clínica', d: 'Imagen o PDF · la IA actualiza tu ficha' },
];

export function SaludMenu() {
  const navigate = useNavigate();
  return (
    <div className="h-full flex flex-col">
      <ScreenHeader title="Mi salud" subtitle="Tu información médica en un solo lugar" />
      <div className="flex-1 overflow-y-auto scrollhide px-5 pt-2.5 pb-[90px] flex flex-col gap-2.5">
        {MENU.map((m) => (
          <ListRow key={m.id} icon={m.icon} title={m.t} subtitle={m.d} trailing={<Chevron />} onClick={() => navigate(`/app/salud/${m.id}`)} />
        ))}
      </div>
    </div>
  );
}
