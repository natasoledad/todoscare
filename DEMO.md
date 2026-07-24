# Demo interactivo de TODOSCARE

Guía para levantar la app y navegarla en vivo (los 8 módulos, 5 roles), con
datos de demostración precargados.

## Opción A — Docker (recomendada, 1 comando)

**Requisito:** Docker Desktop (Windows/Mac) o Docker + Compose (Linux).

```bash
# 1) clonar y entrar al repo
git clone https://github.com/natasoledad/todoscare.git
cd todoscare

# 2) preparar variables (la primera vez, con datos demo)
cp .env.prod.example .env
#   edita .env y pon:  SEED_ON_START=true
#   (en Windows PowerShell:  copy .env.prod.example .env  y editar con notepad .env)

# 3) levantar los 3 servicios (Postgres + API + web)
docker compose -f docker-compose.prod.yml up -d --build

# 4) esperar ~30 s a que migre y siembre, y abrir:
#    http://localhost
```

Verificar salud: `curl http://localhost/api/health` → `{"status":"ok"}`

> Tras el primer arranque, vuelve a poner `SEED_ON_START=false` en `.env`
> (así no re-siembra en cada reinicio). Para parar: `docker compose -f
> docker-compose.prod.yml down`. Para borrar también los datos: agrega `-v`.

## Opción B — sin Docker (modo desarrollo)

**Requisitos:** Python 3.11, Node 20, PostgreSQL 16.

```bash
# Backend
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"   # Win: .venv\Scripts\pip
cp .env.example .env
# crear la BD y extensiones:
#   createdb todoscare && psql -d todoscare -c "CREATE EXTENSION pgcrypto; CREATE EXTENSION btree_gist;"
.venv/bin/alembic upgrade head && .venv/bin/python -m app.seed
.venv/bin/uvicorn app.main:app --reload            # API en :8000

# Frontend (otra terminal)
cd frontend && npm install && npm run dev           # PWA en :5173  (proxya /api a :8000)
```

Abrir **http://localhost:5173**.

## Opción C — demo compartible (con enlace público)

Sigue **[DEPLOY.md](DEPLOY.md)**: el mismo `docker-compose.prod.yml` detrás de
un dominio con TLS (balanceador gestionado o Traefik/Caddy con Let's Encrypt).
Fija `CORS_ORIGINS` y un `JWT_SECRET` fuerte.

---

## Usuarios demo (contraseña `Demo1234!`)

| Correo | Rol | Entra a |
|---|---|---|
| `paciente.a@todoscare.dev` | Paciente | `/app` |
| `medico.a@todoscare.dev` | Médico (Dra. Nátaly) | `/medico` |
| `empresa.a@todoscare.dev` | Empresa / Clínica | `/empresa` |
| `super@todoscare.dev` | Super-Admin (toda la plataforma) | `/admin` |
| `admin.a@todoscare.dev` | Admin de una clínica | `/admin` |
| `aseguradora.x@todoscare.dev` | Aseguradora / Prestador | `/aseguradora` |

## Guion sugerido (qué mostrar en cada rol)

1. **Paciente** — inicia sesión: mira Inicio (nivel/puntos), abre **Agenda**
   y reserva una cita (el backend impide la doble-reserva), entra a **Mi
   salud → QR de emergencia**, y prueba el **Asistente por WhatsApp**
   ("¿cuándo es mi próxima cita?").
2. **Médico** — su **Agenda del día** (cita con Camila), abre la **ficha**
   (acceso auditado), registra una **atención**, intenta **prescribir** un
   alérgeno (bloqueo clínico), **cierra** la atención (genera el split) y ve
   **Mis liquidaciones**.
3. **Empresa** — KPIs, crea un **servicio** (aparece en el catálogo del
   paciente), una **promo**, y en **Indicadores (CRM) → Marketing digital**
   revisa las **campañas** y la **Atribución** (ROI real por campaña).
4. **Administrador** (`super@`) — **alta de una clínica** (nuevo tenant),
   publica **T&C** de un país (el paciente de ese país queda con
   re-aceptación pendiente), **CRM** consolidado con drill-down, ledger
   inmutable, **auditoría** e **integraciones** (activa/desactiva conectores).
5. **Aseguradora** — resuelve una **autorización** (nota el "mínimo dato
   clínico"), gestiona **convenios/aranceles**, y **liquida** a la clínica
   (sube y baja las Cuentas por Cobrar del CRM).

## Conectores para mostrar en vivo (cruce entre roles)

- Empresa crea un servicio/agenda → aparece para el **Paciente**.
- Paciente reserva → entra en la **Agenda del Médico**.
- Médico cierra atención → sube los **ingresos del CRM** (Empresa/Admin).
- Admin publica T&C → **re-aceptación** obligatoria del Paciente.
- Aseguradora liquida → mueve las **Cuentas por Cobrar** del CRM.
- Paciente atribuido a una campaña → **ROI real** en Marketing (Empresa/Admin).
