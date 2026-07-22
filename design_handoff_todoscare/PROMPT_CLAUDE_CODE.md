# Prompt inicial para Claude Code — TODOSCARE

Copia y pega el bloque de abajo en Claude Code, abierto dentro de la carpeta donde descomprimiste el handoff.

---

Estoy construyendo TODOSCARE, una plataforma médica/odontológica multi-tenant (SaaS), mobile-first como PWA (abre en webview de WhatsApp o Chrome — NO app nativa de tiendas).

**Antes de escribir código, lee estos archivos del bundle en esta carpeta:**
1. `design_handoff_todoscare/README.md` (visión, tokens, pantallas, stack).
2. Todas las specs en `design_handoff_todoscare/specs/` (una por rol).
3. Abre `design_handoff_todoscare/prototypes/TODOSCARE App Prototype (standalone).html` en el navegador para ver el diseño de referencia.

**Stack a usar:**
- Backend: Python + FastAPI (async), PostgreSQL 13+ (pgcrypto, btree_gist), SQLAlchemy async, JWT + bcrypt.
- Frontend: React + Vite + TypeScript + Tailwind, como PWA.

**Reglas transversales (aplican a todo):**
- Multi-tenant estricto: toda query valida `clinic_id`; nunca cruzar datos entre tenants.
- RBAC contextual: rol vinculado a clínica/sucursal. Respetar la matriz Ver/Crear/Editar/Eliminar de cada spec.
- Ledger financiero inmutable; prontuario clínico como JSONB; agenda con índice anti doble-reserva (GiST).
- Acceso al dato clínico solo por el profesional tratante, siempre auditado.
- T&C versionados por país (Chile, Brasil, Colombia, México) con re-aceptación obligatoria.
- El HTML del bundle es SOLO referencia visual — recréalo en React+Tailwind, no lo copies.

**Orden de implementación (hazlo por fases, y detente al final de cada una para que yo revise):**
1. Andamiaje del proyecto (estructura backend + frontend PWA, config, base de datos, auth JWT, modelo RBAC multi-tenant).
2. Rol Paciente: registro (5 campos + T&C), onboarding (5 preguntas + dependientes), app principal (tabs Inicio/Agenda/Salud/Farmacia/Perfil), billetera, QR de emergencia. Sigue `Spec Paciente`.
3. Rol Médico: agenda, atención/prontuario, prescripción, órdenes de examen. Sigue `Spec Medico`.
4. Rol Empresa/Cliente: agendas, catálogo+precios, promociones. Sigue `Spec Empresa Cliente`.
5. Rol Administrador: multi-tenant, usuarios/roles, planes, config global. Sigue `Spec Administrador`.
6. CRM financiero (indicadores + conectores). Sigue `Spec CRM Clinicas`.
7. Rol Aseguradora/Prestador (convenios, autorizaciones, liquidaciones). Sigue `Spec Aseguradora Prestador`.
8. Integraciones: WhatsApp/IA, laboratorio, farmacia, pasarela de pago + split, mapas, web push.

Empieza por la Fase 1: propón la estructura de carpetas y el esquema de base de datos, y espera mi OK antes de continuar.

---

**Nota:** si ya tienes código de backend iniciado (las fases de tablas que mencionaste), cópialo en esta carpeta antes de correr el prompt y agrega al inicio: "Ya existe un backend parcial en `<ruta>`; úsalo como base en lugar de crear uno nuevo."
