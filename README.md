# TODOSCARE

Plataforma médica/odontológica multi-tenant (SaaS), mobile-first PWA (React
Native webview / WhatsApp / Chrome — sin apps nativas de tienda).

Implementado a partir del handoff de diseño en `design_handoff_todoscare/`
(prototipo + specs funcionales por rol). Ver ese README para tokens de
diseño, pantallas y el detalle de cada rol.

## Estado — Fase 1 (andamiaje)

✅ Backend: estructura, esquema de base de datos (39 tablas), migración
Alembic aplicada, auth JWT, motor RBAC/tenant multi-clínica.
⏳ Frontend, CRUDs de negocio por rol: fases siguientes.

## Stack

- **Backend**: Python 3.11 + FastAPI (async) + SQLAlchemy 2.0 (async) +
  PostgreSQL 16 (pgcrypto, btree_gist) + Alembic + JWT (python-jose) +
  bcrypt (passlib).
- **Frontend**: React + Vite + TypeScript + Tailwind (PWA) — fase 2+.

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

Prueba de humo (RBAC + aislamiento multi-tenant, end-to-end contra la BD real):

```bash
.venv/bin/python -m tests.test_rbac_smoke
```

## Estructura

```
backend/
  app/
    core/       # config, database (async engine), security (JWT/bcrypt), audit (soft-delete)
    tenancy/     # TenantContext, get_current_ctx (JWT -> contexto)
    rbac/        # permisos, matriz por rol (transcrita de cada spec), require()
    models/      # SQLAlchemy — un módulo por dominio
    schemas/     # Pydantic (request/response)
    routers/     # endpoints FastAPI
    seed.py      # datos demo idempotentes
  alembic/       # migraciones
  tests/
frontend/        # fase 2+
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
