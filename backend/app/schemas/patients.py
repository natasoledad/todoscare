import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class ClinicPublicOut(BaseModel):
    id: uuid.UUID
    razon_social: str
    pais: str


class TycVersionOut(BaseModel):
    id: uuid.UUID
    pais: str
    version: str
    contenido: str
    publicado_en: datetime


class RegisterInput(BaseModel):
    nombre: str = Field(min_length=3)
    rut: str = Field(min_length=3)
    telefono: str = Field(min_length=6)
    direccion: str = Field(min_length=3)
    correo: EmailStr
    password: str = Field(min_length=8)
    clinic_id: uuid.UUID
    tyc_version_id: uuid.UUID
    campana_id: uuid.UUID | None = None  # atribución de marketing (UTM/ref)


class DependentIn(BaseModel):
    nombre: str = Field(min_length=1)


class DependentOut(BaseModel):
    id: uuid.UUID
    nombre: str


class OnboardingAnswers(BaseModel):
    motivo: str | None = None
    condicion: str | None = None
    actividad: str | None = None
    alergias: str | None = None
    seguro: str | None = None


class OnboardingInput(BaseModel):
    answers: OnboardingAnswers
    dependents: list[DependentIn] = []


class WalletOut(BaseModel):
    puntos: int
    cashback: float


class PatientMeOut(BaseModel):
    id: uuid.UUID
    nombre: str
    correo: EmailStr
    telefono: str
    direccion: str
    rut: str
    nivel: str
    onboarding_completado: bool
    tyc_pendiente: bool  # el admin publicó una versión de T&C más nueva que la última que aceptó
    wallet: WalletOut
    dependents: list[DependentOut]
    ficha: dict


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FichaUpdateInput(BaseModel):
    """Partial update — every field optional, merged into the existing
    ficha JSONB (Spec Paciente §2.2, campos opcionales editables)."""

    fecha_nacimiento: str | None = None
    sexo: str | None = None
    contacto_emergencia: str | None = None
    grupo_sanguineo: str | None = None
    alergias: str | None = None
    medicacion_actual: str | None = None
    antecedentes: str | None = None
    seguro: str | None = None
