"""Datos ficticios para PRUEBAS de Higia — "Clínica Visión" (Chile).

Idempotente. Correr con:  python -m app.seed_higia

Crea un centro médico-dental listo para probar la gestión (portal Empresa) y el
lado profesional (prestador):

  · Clínica Visión (país CL) + sede central + accesos de gestión (portal
    Empresa y Administrador de clínica).
  · 4 médicos y 3 dentistas con agenda de lunes a sábado, 09:00–15:00, cada uno
    con su cadencia de horas (la cadencia la fija la duración del servicio):
        médicos    → 15, 20, 30 y 60 min
        dentistas  → 30 (general), 60 (periodoncia) y 30 (ortodoncia) min
  · 3 pacientes (Saulo Batistela, Natalia Silva, Joaquín Aburto) con ficha
    clínica, exámenes previos (laboratorio, Rx, ecografía), odontograma y
    algunas citas (pasadas y próximas) para poblar las agendas.

Nota: las prestaciones médicas/odontológicas se crean EXENTAS de IVA (Chile,
D.L. 825 Art. 12 E) — coincide con la lógica tributaria de la plataforma.

Contraseña de TODOS los usuarios (pacientes y profesionales/gestión): 123mudar
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.catalog import CatalogItem, Specialty
from app.models.clinical import EmergencyQr, ExamOrder, ExamResult, Hospitalization, MedicalRecord, Odontogram
from app.models.identity import User
from app.models.patient import Patient, TycAcceptance
from app.models.scheduling import Appointment, AvailabilityBlock
from app.models.wallet import WalletAccount
from app.rbac.permissions import RoleCode
from app.seed import (
    assign_role,
    get_or_create_branch,
    get_or_create_clinic,
    get_or_create_role,
    get_or_create_specialty,
    get_or_create_tyc,
)

PASSWORD = "123mudar"  # pacientes y profesionales/gestión (entorno de prueba)

# ── Profesionales: (nombre, email, especialidad, ícono, cadencia_min, precio) ──
# La "agenda de N en N minutos" la determina la duración del servicio del
# profesional; cada uno tiene su propia especialidad para no mezclar cadencias.
MEDICOS = [
    ("Dra. Victoria Catarina", "victoriacatarinabls@gmail.com", "Medicina General", "🩺", 15, 30000),
    ("Dr. Tomás Herrera",      "tomas.herrera.higia@gmail.com", "Pediatría",        "🧒", 20, 32000),
    ("Dra. Paula Moretti",     "paula.moretti.higia@gmail.com", "Cardiología",      "❤️", 30, 45000),
    ("Dr. Ignacio Fuentes",    "ignacio.fuentes.higia@gmail.com", "Ginecología",    "🌸", 60, 50000),
]
DENTISTAS = [
    ("Dr. Bruno Batistela", "bancobastitela@gmail.com",      "Odontología General", "🦷", 30, 35000),
    ("Dra. Elena Vidal",    "elena.vidal.higia@gmail.com",   "Periodoncia",         "🦿", 60, 55000),
    ("Dr. Martín Soto",     "martin.soto.higia@gmail.com",   "Ortodoncia",          "😬", 30, 48000),
]

# ── Pacientes: (nombre, email, rut, dirección, ficha, exámenes) ──
PACIENTES = [
    {
        "nombre": "Saulo Batistela",
        "email": "saulobatistela@gmail.com",
        "rut": "26.482.157-3",
        "direccion": "Av. Providencia 2134, depto 802, Providencia, Santiago",
        "ficha": {
            "fecha_nacimiento": "1988-02-17", "sexo": "Masculino", "grupo_sanguineo": "A+",
            "alergias": "Ninguna conocida", "medicacion_actual": "Ninguna",
            "antecedentes": "Fractura de tobillo (2015). Sin patologías crónicas.",
            "contacto_emergencia": "Natalia Silva +56 9 5921 5416", "seguro": "Sí",
        },
        "medico_idx": 0,   # Dra. Victoria (Medicina General)
        "dentista_idx": 0, # Dr. Bruno (Odontología General)
        "examenes": [
            ("laboratorio", "Hemograma completo", {"Hemoglobina": "15.1 g/dL", "Leucocitos": "6.800 /µL", "Plaquetas": "245.000 /µL", "conclusion": "Dentro de rango normal"}),
            ("laboratorio", "Perfil lipídico", {"Colesterol total": "192 mg/dL", "HDL": "51 mg/dL", "LDL": "118 mg/dL", "Triglicéridos": "140 mg/dL", "conclusion": "Límite normal-alto"}),
            ("imagenes", "Radiografía de tórax (PA)", {"tecnica": "Rx tórax PA y lateral", "conclusion": "Campos pulmonares libres. Silueta cardíaca normal."}),
        ],
    },
    {
        "nombre": "Natalia Silva",
        "email": "saulobatistela@hotmail.com",
        "rut": "24.117.905-6",
        "direccion": "Calle Los Aromos 455, Ñuñoa, Santiago",
        "ficha": {
            "fecha_nacimiento": "1992-09-03", "sexo": "Femenino", "grupo_sanguineo": "O+",
            "alergias": "AINEs (ibuprofeno)", "medicacion_actual": "Anticonceptivo oral",
            "antecedentes": "Migraña ocasional.", "contacto_emergencia": "Saulo Batistela +56 9 5921 5416", "seguro": "Sí",
        },
        "medico_idx": 2,   # Dra. Paula (Cardiología)
        "dentista_idx": 1, # Dra. Elena (Periodoncia)
        "examenes": [
            ("laboratorio", "Glicemia en ayunas", {"Glucosa": "88 mg/dL", "conclusion": "Normal"}),
            ("imagenes", "Ecografía abdominal", {"tecnica": "Ecotomografía abdominal", "conclusion": "Hígado, vesícula y riñones sin hallazgos. Sin líquido libre."}),
            ("laboratorio", "Orina completa", {"Aspecto": "Claro", "Leucocitos": "Negativo", "conclusion": "Sin signos de infección"}),
        ],
    },
    {
        "nombre": "Joaquín Aburto",
        "email": "saulobatistela12@gmail.com",
        "rut": "25.903.446-1",
        "direccion": "Pasaje El Roble 78, Maipú, Santiago",
        "ficha": {
            "fecha_nacimiento": "1979-11-28", "sexo": "Masculino", "grupo_sanguineo": "B+",
            "alergias": "Ninguna conocida", "medicacion_actual": "Losartán 50 mg/día",
            "antecedentes": "Hipertensión arterial (2020). Controlada.",
            "contacto_emergencia": "Saulo Batistela +56 9 5921 5416", "seguro": "No",
        },
        "medico_idx": 2,   # Dra. Paula (Cardiología) — control de su hipertensión
        "dentista_idx": 2, # Dr. Martín (Ortodoncia)
        "examenes": [
            ("imagenes", "Radiografía panorámica dental", {"tecnica": "Ortopantomografía", "conclusion": "Piezas presentes. Reabsorción ósea leve zona molar inferior."}),
            ("laboratorio", "Hemograma completo", {"Hemoglobina": "14.4 g/dL", "Leucocitos": "7.100 /µL", "conclusion": "Normal"}),
            ("imagenes", "Ecografía tiroidea", {"tecnica": "Eco tiroides", "conclusion": "Glándula de tamaño normal, sin nódulos."}),
        ],
    },
]


async def upsert_user(db, email: str, nombre: str, telefono: str | None = None) -> User:
    """Crea o actualiza el usuario (reaplica la contraseña de prueba en cada
    corrida, para que re-ejecutar el seed deje los accesos siempre válidos)."""
    row = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if row is None:
        row = User(email=email, password_hash=hash_password(PASSWORD), nombre=nombre, telefono=telefono)
        db.add(row)
        await db.flush()
        return row
    row.nombre = nombre
    row.password_hash = hash_password(PASSWORD)
    if telefono:
        row.telefono = telefono
    return row


def _next_business_day(base: datetime, delta_days: int) -> datetime:
    """base + delta_days, corrido al día siguiente si cae domingo (lun–sáb)."""
    d = base + timedelta(days=delta_days)
    if d.weekday() == 6:  # domingo
        d += timedelta(days=1)
    return d


async def _seed_professional(db, clinic, branch, nombre, email, especialidad, icono, cadencia, precio, telefono):
    """Usuario + rol médico + especialidad + servicio (con la cadencia) +
    agenda lun–sáb 09:00–15:00 por las próximas ~4 semanas."""
    roles = {code.value: await get_or_create_role(db, code.value) for code in (RoleCode.MEDICO,)}
    user = await upsert_user(db, email, nombre, telefono)
    await assign_role(db, user.id, roles[RoleCode.MEDICO.value].id, clinic_id=clinic.id, branch_id=branch.id)

    specialty = await get_or_create_specialty(db, especialidad, icono)

    # Servicio del profesional: su duración fija la cadencia de la agenda.
    servicio = (
        await db.execute(
            select(CatalogItem).where(CatalogItem.clinic_id == clinic.id, CatalogItem.nombre == f"{especialidad} — consulta", CatalogItem.tipo == "servicio")
        )
    ).scalar_one_or_none()
    if servicio is None:
        servicio = CatalogItem(
            clinic_id=clinic.id, specialty_id=specialty.id, tipo="servicio",
            nombre=f"{especialidad} — consulta", precio=precio, duracion_min=cadencia,
            afecto_iva=False,  # prestación de salud exenta de IVA (Chile)
        )
        db.add(servicio)
        await db.flush()

    # Agenda: lun–sáb, 09:00–15:00, próximas 4 semanas (idempotente por profesional).
    ya_tiene = (await db.execute(select(AvailabilityBlock).where(AvailabilityBlock.professional_id == user.id))).scalars().first()
    if ya_tiene is None:
        hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        for delta in range(0, 28):
            dia = hoy + timedelta(days=delta)
            if dia.weekday() == 6:  # domingo: cerrado
                continue
            db.add(
                AvailabilityBlock(
                    clinic_id=clinic.id, branch_id=branch.id, professional_id=user.id,
                    specialty_id=specialty.id,
                    rango=Range(dia + timedelta(hours=9), dia + timedelta(hours=15)),
                    reglas={"duracion_min": cadencia, "dias": "lun-sab", "horario": "09:00-15:00"},
                )
            )
    return user, servicio


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Roles + T&C de Chile.
        for code in RoleCode:
            await get_or_create_role(db, code.value)
        tyc_cl = await get_or_create_tyc(db, "CL")

        clinic = await get_or_create_clinic(db, "Clínica Visión", "CL")
        branch = await get_or_create_branch(db, clinic.id, "Clínica Visión — Sede Central")
        if branch.direccion is None:
            branch.direccion = "Av. Nueva Providencia 1881, Providencia, Santiago"
            branch.geo = {"lat": -33.4265, "lng": -70.6167}

        # ── Gestión del centro (Clínica Visión Empresa) ──
        gestion = await upsert_user(db, "gestion@clinicavision.cl", "Clínica Visión (gestión)")
        await assign_role(db, gestion.id, (await get_or_create_role(db, RoleCode.EMPRESA.value)).id, clinic_id=clinic.id)
        admin = await upsert_user(db, "admin@clinicavision.cl", "Administración Clínica Visión")
        await assign_role(db, admin.id, (await get_or_create_role(db, RoleCode.CLINIC_ADMIN.value)).id, clinic_id=clinic.id)

        # ── Profesionales (prestadores) ──
        profesionales: list[tuple[User, CatalogItem]] = []
        for nombre, email, esp, icono, cad, precio in MEDICOS + DENTISTAS:
            profesionales.append(await _seed_professional(db, clinic, branch, nombre, email, esp, icono, cad, precio, None))

        await db.commit()

        # ── Pacientes: usuario + ficha + wallet + T&C + exámenes + citas ──
        for i, p in enumerate(PACIENTES):
            user = await upsert_user(db, p["email"], p["nombre"], telefono="+56959215416")
            await assign_role(db, user.id, (await get_or_create_role(db, RoleCode.PACIENTE.value)).id, clinic_id=clinic.id)

            patient = (await db.execute(select(Patient).where(Patient.user_id == user.id))).scalar_one_or_none()
            if patient is None:
                patient = Patient(
                    clinic_id=clinic.id, user_id=user.id, rut=p["rut"], direccion=p["direccion"],
                    onboarding_completado=True, ficha_completa_bonus_otorgado=True, ficha=p["ficha"],
                )
                db.add(patient)
                await db.flush()
                db.add(TycAcceptance(patient_id=patient.id, tyc_version_id=tyc_cl.id, aceptado_en=datetime.now(timezone.utc)))
                db.add(WalletAccount(clinic_id=clinic.id, patient_id=patient.id))
            else:
                patient.rut = p["rut"]
                patient.direccion = p["direccion"]
                patient.ficha = p["ficha"]

            medico_user, medico_serv = profesionales[p["medico_idx"]]
            dentista_user, dentista_serv = profesionales[len(MEDICOS) + p["dentista_idx"]]

            # Exámenes previos (realizados) — solo si aún no tiene.
            tiene_examenes = (await db.execute(select(ExamOrder).where(ExamOrder.patient_id == patient.id))).scalars().first()
            if tiene_examenes is None:
                now = datetime.now(timezone.utc)
                for j, (tipo, nombre_ex, resultado) in enumerate(p["examenes"]):
                    order = ExamOrder(clinic_id=clinic.id, patient_id=patient.id, professional_id=medico_user.id, tipo=tipo, estado="listo")
                    db.add(order)
                    await db.flush()
                    order.created_at = now - timedelta(days=30 + j * 10)
                    db.add(ExamResult(clinic_id=clinic.id, order_id=order.id, resultado={"nombre": nombre_ex, **resultado}, estado="listo"))

                # Ficha clínica (prontuario) del médico tratante.
                db.add(MedicalRecord(
                    clinic_id=clinic.id, patient_id=patient.id, professional_id=medico_user.id,
                    contenido={
                        "motivo": "Control de salud",
                        "anamnesis": f"Paciente {p['ficha']['sexo'].lower()}, antecedentes: {p['ficha']['antecedentes']}",
                        "examen_fisico": "Signos vitales estables. Examen segmentario sin hallazgos relevantes.",
                        "diagnostico": "Paciente en buenas condiciones generales.",
                        "plan": "Continuar controles habituales. Se solicitan exámenes de rutina.",
                    },
                ))

                # Odontograma (para probar el módulo dental).
                db.add(Odontogram(
                    clinic_id=clinic.id, patient_id=patient.id,
                    piezas={str(k): {"estado": "pendiente" if k in (14, 36) else "sana"} for k in range(11, 48)},
                ))

                # QR de emergencia.
                db.add(EmergencyQr(
                    clinic_id=clinic.id, patient_id=patient.id, token=f"higia-qr-{i + 1}",
                    resumen={"grupo_sanguineo": p["ficha"]["grupo_sanguineo"], "alergias": p["ficha"]["alergias"]},
                ))

                if i == 2:  # una hospitalización de ejemplo
                    db.add(Hospitalization(clinic_id=clinic.id, patient_id=patient.id, motivo="Observación por crisis hipertensiva", centro="Clínica Santa María", ingreso=datetime(2021, 6, 4).date(), egreso=datetime(2021, 6, 6).date()))

            # Citas: una pasada (completada) con su médico y una próxima con su dentista.
            tiene_citas = (await db.execute(select(Appointment).where(Appointment.patient_id == patient.id))).scalars().first()
            if tiene_citas is None:
                hoy = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                # Hora distinta por paciente (09/10/11 y 12/13/14): así no colisionan
                # aunque compartan profesional y el mismo día tras ajustar domingos.
                pasada = _next_business_day(hoy, -7 - i) + timedelta(hours=9 + i)
                proxima = _next_business_day(hoy, 3 + i) + timedelta(hours=12 + i)
                db.add(Appointment(
                    clinic_id=clinic.id, branch_id=branch.id, professional_id=medico_user.id, patient_id=patient.id,
                    service_id=medico_serv.id, slot=Range(pasada, pasada + timedelta(minutes=medico_serv.duracion_min)), estado="completada",
                ))
                db.add(Appointment(
                    clinic_id=clinic.id, branch_id=branch.id, professional_id=dentista_user.id, patient_id=patient.id,
                    service_id=dentista_serv.id, slot=Range(proxima, proxima + timedelta(minutes=dentista_serv.duracion_min)), estado="confirmada",
                ))

        await db.commit()

    # ── Resumen de accesos ──
    print("Seed 'Clínica Visión' OK. Contraseña de TODOS los usuarios:", PASSWORD)
    print("\nGestión del centro (Clínica Visión Empresa):")
    print("  gestion@clinicavision.cl   -> portal Empresa (gestión: agenda, cajas, servicios, tributario, CRM)")
    print("  admin@clinicavision.cl     -> Administrador de la clínica")
    print("\nMédicos (prestadores):")
    for nombre, email, esp, _icono, cad, _precio in MEDICOS:
        print(f"  {email:34s} -> {nombre} · {esp} · agenda {cad} min · lun-sáb 09:00-15:00")
    print("\nDentistas (prestadores):")
    for nombre, email, esp, _icono, cad, _precio in DENTISTAS:
        print(f"  {email:34s} -> {nombre} · {esp} · agenda {cad} min · lun-sáb 09:00-15:00")
    print("\nPacientes (con ficha y exámenes previos):")
    for p in PACIENTES:
        print(f"  {p['email']:30s} -> {p['nombre']} · tel +56959215416")


if __name__ == "__main__":
    asyncio.run(main())
