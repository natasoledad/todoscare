import { useParams } from 'react-router-dom';
import { Campanas } from '../../crm/Campanas';

/** Marketing digital de una clínica desde el drill-down del Admin. */
export function CampanasClinica() {
  const { clinicId } = useParams<{ clinicId: string }>();
  return <Campanas clinicId={clinicId} backTo={`/admin/crm/${clinicId}`} />;
}
