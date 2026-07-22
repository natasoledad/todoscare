# TODOSCARE — frontend (Rol Paciente)

PWA React + Vite + TypeScript + Tailwind CSS implementando el Rol Paciente
(Spec Paciente): registro, onboarding, agenda, mi salud (ficha, exámenes,
dental, hospitalizaciones, agendamientos, QR de emergencia, subir info),
farmacia, perfil y billetera.

Sin datos simulados — `src/api/client.ts` es un cliente real contra el
backend FastAPI (ver `../backend`); en desarrollo, Vite proxya las rutas de
API a `localhost:8000` (ver `vite.config.ts`).

## Desarrollo

```bash
npm install
npm run dev
```

Requiere el backend corriendo (`cd ../backend && .venv/bin/uvicorn app.main:app --reload`),
con la base de datos migrada y sembrada (`.venv/bin/python -m app.seed`).

## Estructura

- `src/api/` — cliente tipado (`client.ts`) y tipos (`types.ts`) para cada endpoint del backend.
- `src/context/AuthContext.tsx` — sesión (JWT + perfil del paciente), login/registro/logout.
- `src/components/` — sistema de diseño compartido (Button, TabBar, ListRow, BottomSheet, ...).
- `src/routes/patient/` — App shell + pestañas Inicio/Agenda/Farmacia/Perfil/Billetera.
- `src/routes/salud/` — submenú "Mi salud" (ficha, exámenes, dental, hospitalizaciones, agendamientos, QR, subir).
- `src/routes/QrResolve.tsx` — página `/qr/:token` a la que apunta el QR de emergencia (requiere login de un usuario con rol médico).

## Build

```bash
npm run build
```
