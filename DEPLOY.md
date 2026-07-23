# Despliegue de TODOSCARE

Arquitectura de producción (3 contenedores):

```
              ┌────────────────────────────────────────────┐
   internet ──►  web (nginx)  ── /api/* ──►  api (FastAPI/gunicorn)  ──►  db (Postgres 16)
              │   SPA (PWA)      /files/*                                  volumen persistente
              └────────────────────────────────────────────┘
```

- **web**: la SPA compilada (Vite) servida por nginx. Hace fallback a
  `index.html` para el routing del lado cliente y **proxya `/api/*` al
  backend** (quitando el prefijo). El prefijo `/api` evita que rutas del SPA
  como `/medico` o `/admin` colisionen con las de la API al recargar.
- **api**: FastAPI bajo gunicorn con workers uvicorn. Al arrancar espera a la
  base, aplica migraciones y (opcional) siembra datos demo.
- **db**: PostgreSQL 16 con las extensiones `pgcrypto` y `btree_gist`.

## Requisitos

- Docker + Docker Compose v2.
- Un dominio y terminación TLS (recomendado por delante, en un balanceador o
  un nginx/traefik con Let's Encrypt).

## Puesta en marcha

```bash
cp .env.prod.example .env
# EDITA .env:  POSTGRES_PASSWORD, DATABASE_URL (misma clave), JWT_SECRET
#   openssl rand -hex 32   # para JWT_SECRET
#   CORS_ORIGINS=https://tu-dominio

# Primer arranque con datos demo (opcional): pon SEED_ON_START=true en .env
docker compose -f docker-compose.prod.yml up -d --build

# Verifica
docker compose -f docker-compose.prod.yml ps
curl -fsS http://localhost/api/health      # {"status":"ok"}
```

Tras el primer arranque, si sembraste, vuelve a poner `SEED_ON_START=false`.

La app queda en `http://localhost` (o el `WEB_PORT` que definas). Usuarios
demo (si sembraste), contraseña `Demo1234!`: `paciente.a@`, `medico.a@`,
`empresa.a@`, `admin.a@`, `super@`, `aseguradora.x@todoscare.dev`.

## Operación

```bash
# Logs
docker compose -f docker-compose.prod.yml logs -f api

# Migraciones (se aplican solas al arrancar; para forzar manualmente):
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# Backup de la base
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U todoscare todoscare > backup_$(date +%F).sql

# Restaurar
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T db \
  psql -U todoscare todoscare
```

## TLS / dominio

El servicio `web` escucha en HTTP (puerto 80). En producción termina TLS
por delante:

- **Opción A** — balanceador gestionado (ALB, Cloud Load Balancer) que
  enruta 443 → `web:80`.
- **Opción B** — un reverse-proxy (Traefik / nginx / Caddy) con Let's Encrypt
  delante del compose.

Fija `CORS_ORIGINS` al dominio público con `https://`.

## Checklist antes de producción

- [ ] `JWT_SECRET` fuerte y único (no el de ejemplo).
- [ ] `POSTGRES_PASSWORD` fuerte; `DATABASE_URL` con la misma clave.
- [ ] `SEED_ON_START=false` (los datos demo son solo para evaluar).
- [ ] TLS terminado por delante; `CORS_ORIGINS` con el dominio real.
- [ ] Backups automáticos del volumen `todoscare_pgdata`.
- [ ] Rotar el `JWT_SECRET` invalida las sesiones vivas (planificado).
- [ ] (Postgres gestionado) habilitar `pgcrypto` y `btree_gist` si el rol de
      la app no puede `CREATE EXTENSION` — ver `docker/initdb/`.
- [ ] Revisar el TODO de inmutabilidad del ledger: crear un rol de app con
      `REVOKE UPDATE, DELETE ON ledger_entries` (ver migración inicial).

## Integración continua

`.github/workflows/ci.yml` levanta Postgres, corre las **8 suites de humo**
(reseteando el esquema entre cada una) y compila el frontend (typecheck +
build) en cada push/PR.

## Desarrollo local (sin Docker)

Backend:
```bash
cd backend
uv venv .venv && uv pip install -e ".[dev]" --python .venv/bin/python
cp .env.example .env
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload
```
Frontend (proxya `/api` a `localhost:8000`):
```bash
cd frontend && npm install && npm run dev
```
