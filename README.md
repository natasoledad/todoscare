# TODOSCARE

Plataforma médica/odontológica multi-tenant (SaaS), mobile-first PWA (React
Native webview / WhatsApp / Chrome — sin apps nativas de tienda).

Implementado a partir del handoff de diseño en `design_handoff_todoscare/`
(prototipo + specs funcionales por rol). Ver ese README para tokens de
diseño, pantallas y el detalle de cada rol.

## Estado

✅ **Fase 1** — andamiaje backend: esquema de base de datos (39 tablas),
migración Alembic aplicada, auth JWT, motor RBAC/tenant multi-clínica.

✅ **Fase 2** — Rol Paciente completo: registro (5 campos + T&C
versionados), onboarding (5 preguntas + dependientes + gamificación),
agenda (disponibilidad real, reserva con anti doble-reserva real,
cancelar), salud (ficha editable, exámenes con subida de archivo real,
odontograma, hospitalizaciones, QR de emergencia real y auditado),
farmacia, billetera — backend + frontend PWA (React+Vite+TS+Tailwind),
verificado end-to-end contra Postgres real y en navegador.

✅ **Fase 3** — Rol Médico completo: agenda del día, ficha del paciente
con aislamiento clínico real (solo pacientes que atiende, cada acceso
auditado en `audit_logs`), prontuario JSONB con enmienda auditada
(nunca borrado), prescripción con firma inmutable + reemisión
(anula+reemite) + bloqueo por alerta de alergia antes de firmar, órdenes
de examen (que aparecen en la app del paciente), odontograma editable, y
cierre de atención que genera ingreso en el ledger + split de pago al
profesional (liquidaciones).

✅ **Fase 4** — Rol Empresa/Cliente completo: portal con KPIs de la
clínica (citas hoy, ingresos del mes, servicios más vendidos, promos
activas), configurar agendas (bloques de disponibilidad reales que se
vuelven horarios para el paciente), catálogo de servicios con precios
(alta/edición/baja lógica que se refleja en el catálogo del paciente),
promociones (crear/activar/pausar), información de la empresa, y
funcionarios B2B (alta/baja de nómina). Todo acotado a su `clinic_id`.

✅ **Fase 5** — Rol Administrador completo (multi-tenant): KPIs de
plataforma con alcance según el rol (super_admin ve todos los tenants;
clinic_admin solo su clínica), alta de clínica (nuevo tenant: crea
`Clinic` + primera `Branch` + usuario admin + `RoleAssignment`
`clinic_admin` en un solo paso) y baja lógica con doble confirmación,
gestión de usuarios y roles, planes y precios, T&C versionados por país
(publicar una versión nueva obliga a re-aceptación de los pacientes de ese
país — flag `tyc_pendiente`), finanzas con **ledger inmutable de solo
lectura** (sin endpoint de edición/borrado) y auditoría que muestra
**solo metadatos** (nunca contenido clínico). Todo respeta el aislamiento
multi-tenant y la matriz Ver/Crear/Editar/Eliminar del rol.

✅ **Fase 7** — Rol Aseguradora / Prestador (Spec Aseguradora Prestador). El
tercero pagador se vincula a su **entidad aseguradora** (no a un tenant
clínico): ve los convenios de su red, su padrón y sus autorizaciones, nunca
los de otra aseguradora. Cubre: convenios y **aranceles versionados**
(cobertura % + copago por servicio), padrón de afiliados con vigencia (alta/
baja), **resolución de autorizaciones** (aprobar/rechazar con motivo/pedir
info, validando vigencia del afiliado), **liquidación a la clínica**
(generar factura la atención → asiento `facturado` que sube las Cuentas por
Cobrar del CRM; pagar → asiento `cobrado` que las baja, ambos inmutables e
idempotentes) y la **ficha del afiliado bajo minimización**: solo se abre si
hay una autorización aprobada, expone lo mínimo (sin prontuario completo) y
queda auditada.

Auth del frontend es multi-rol (`/auth/me`): paciente → `/app`, médico →
`/medico`, empresa → `/empresa`, administrador → `/admin`, aseguradora →
`/aseguradora`.

✅ **Fase 6** — CRM / gestión financiera multi-clínica (Spec CRM Clínicas).
No es un rol propio: lo consumen el Administrador (consolidado global) y la
Empresa/Clínica (acotada a la suya), con el mismo cálculo y distinto
alcance. **Fuente única de verdad**: el CRM no guarda cifras, las calcula
desde el ledger inmutable + la agenda (ingresos, margen, ticket promedio,
ocupación de agenda, cuentas por cobrar, ingresos por servicio, por
liquidar y variación mes-vs-mes). Pantallas: panel consolidado con
drill-down por clínica, detalle de clínica, y **liquidaciones** que se
concilian (marcar pagado ⇒ asiento de egreso inmutable en el ledger, §5.2)
de forma idempotente. Exportación de asientos a ERP (CSV) solo para el
Admin. Todo respeta el aislamiento por `clinic_id` y la matriz de permisos
§7 (empresa ve KPIs de su clínica pero no el consolidado ni la
conciliación por defecto).

✅ **Fase 8** — Integraciones: una capa de conectores externos
(`app/integrations/`) con adaptadores **simulados y deterministas** que
implementan la forma del contrato real sin credenciales ni red (el punto de
enganche de cada proveedor queda documentado en el módulo). Cada conector se
habilita/deshabilita por clínica vía `IntegrationConfig` (uno apagado rechaza
sus eventos) y deja traza en `integration_events`. Conectores: **WhatsApp/IA**
(el asistente del webview responde al paciente con datos reales — próxima
cita, agenda, ficha), **pasarela de pago** (el webhook asienta ingreso + split
en el ledger inmutable y sube los ingresos del CRM; idempotente),
**laboratorio** (webhook de resultado → aparece en Mi Salud), **farmacia**
(webhook de estado de dispensación), **mapas** (sucursales por cercanía,
Haversine) y **web push** (suscripción + buzón de notificaciones). El
Administrador ve y gobierna los conectores y su traza.

Con la Fase 8 quedan cubiertos los ocho módulos del plan (Paciente, Médico,
Empresa, Administrador, CRM, Aseguradora e Integraciones sobre el andamiaje
multi-tenant).

## Stack

- **Backend**: Python 3.11 + FastAPI (async) + SQLAlchemy 2.0 (async) +
  PostgreSQL 16 (pgcrypto, btree_gist) + Alembic + JWT (python-jose) +
  bcrypt (passlib).
- **Frontend**: React + Vite + TypeScript + Tailwind (PWA), en `frontend/`.

## Despliegue

Producción con Docker Compose (Postgres + API con gunicorn + SPA servida por
nginx, que proxya `/api` al backend). Guía completa en **[DEPLOY.md](DEPLOY.md)**:

```bash
cp .env.prod.example .env   # edita JWT_SECRET, POSTGRES_PASSWORD, dominio
docker compose -f docker-compose.prod.yml up -d --build
curl -fsS http://localhost/api/health   # {"status":"ok"}
```

CI (`.github/workflows/ci.yml`) corre las 8 suites de humo y compila el
frontend en cada push/PR.

## Backend — desarrollo local

```bash
cd backend
uv venv .venv && uv pip install -e ".[dev]" --python .venv/bin/python
cp .env.example .env   # ajusta DATABASE_URL si hace falta

# Postgres (local o vía docker-compose desde la raíz del repo)
docker compose up -d db
# o, si ya tienes Postgres 16 corriendo localmente:
#   createuser todoscare --pwprompt --createdb
#   createdb todoscare -O todoscare
#   psql -d todoscare -c "CREATE EXTENSION IF NOT EXISTS pgcrypto; CREATE EXTENSION IF NOT EXISTS btree_gist;"

.venv/bin/alembic upgrade head
.venv/bin/python -m app.seed        # crea 2 clínicas + 1 usuario por rol (password: Demo1234!)
.venv/bin/uvicorn app.main:app --reload
```

Pruebas de humo end-to-end contra la BD real (sin mocks):

```bash
.venv/bin/python -m tests.test_rbac_smoke       # RBAC + aislamiento multi-tenant (Fase 1)
.venv/bin/python -m tests.test_paciente_smoke   # flujo completo Rol Paciente (Fase 2)
.venv/bin/python -m tests.test_medico_smoke     # flujo completo Rol Médico (Fase 3)
.venv/bin/python -m tests.test_empresa_smoke    # flujo completo Rol Empresa (Fase 4)
.venv/bin/python -m tests.test_admin_smoke      # flujo completo Rol Administrador (Fase 5)
.venv/bin/python -m tests.test_crm_smoke        # CRM: consolidado, KPIs, conciliación (Fase 6)
.venv/bin/python -m tests.test_aseguradora_smoke # Aseguradora: convenios, autorizaciones, liquidación (Fase 7)
.venv/bin/python -m tests.test_integraciones_smoke # Integraciones: conectores externos simulados (Fase 8)
```

Usuarios demo médicos (password `Demo1234!`): `medico.a@todoscare.dev`
(Dra. Nátaly, con una cita hoy con Camila) y `medico.b@todoscare.dev`
(Dr. Fuentes, sin citas — sirve para probar el aislamiento clínico).

## Frontend — desarrollo local

```bash
cd frontend
npm install
npm run dev   # proxya /auth, /patients, /agenda, /salud, /farmacia, /billetera, /clinics, /tyc, /files -> localhost:8000
```

Requiere el backend corriendo en `localhost:8000` (ver arriba). Usuarios demo
(password `Demo1234!`): `paciente.a@todoscare.dev` (perfil ya establecido,
con exámenes/receta/wallet seedeados) o crea una cuenta nueva desde
"Crear cuenta nueva".

## Estructura

```
backend/
  app/
    core/       # config, database (async engine), security (JWT/bcrypt), audit (soft-delete)
    tenancy/     # TenantContext, get_current_ctx (JWT -> contexto)
    rbac/        # permisos, matriz por rol (transcrita de cada spec), require()
    models/      # SQLAlchemy — un módulo por dominio
    schemas/     # Pydantic (request/response)
    routers/     # endpoints FastAPI (auth, patients, agenda, salud, farmacia, wallet)
    services/    # gamification (puntos/nivel), scheduling (generación de slots)
    seed.py      # datos demo idempotentes
  alembic/       # migraciones
  tests/         # smoke tests end-to-end contra la BD real
frontend/
  src/
    api/         # cliente tipado real (fetch) + tipos
    components/  # sistema de diseño (Button, TabBar, ListRow, ...)
    context/      # AuthContext (JWT + perfil del paciente)
    routes/       # pantallas — patient/ (tabs), salud/ (submenú Mi salud)
docker-compose.yml
design_handoff_todoscare/   # bundle de diseño original (prototipo + specs)
```

## Reglas transversales (aplican a todo el proyecto)

- **Multi-tenant estricto**: toda tabla de negocio lleva `clinic_id`; el
  aislamiento se refuerza en el repositorio (`TenantContext.clinic_ids()` /
  `require_clinic_access`), no solo confiando en el filtro de cada query.
- **RBAC contextual**: rol vinculado a clínica/sucursal vía
  `role_assignments` (`clinic_id`/`branch_id` nullable — NULL en ambos =
  super_admin cruza todos los tenants).
- **Agenda anti doble-reserva**: `EXCLUDE USING gist` en `appointments`
  (constraint `appointments_no_overlap`) — lo garantiza Postgres, no el
  código de la API.
- **Ledger financiero inmutable**: solo INSERT a nivel de código (sin
  endpoint de edición); ver TODO en la migración inicial para el refuerzo
  a nivel de permisos de BD una vez exista un rol de aplicación dedicado.
- **Soft delete global**: cualquier `session.delete()` sobre un modelo con
  `AuditMixin` se convierte automáticamente en `deleted_at` (ver
  `app/core/audit.py`) — nunca se pierde historial clínico/financiero.
- **T&C versionados por país** (Chile, Brasil, Colombia, México) con
  re-aceptación obligatoria (`tyc_versions` / `tyc_acceptances`).
