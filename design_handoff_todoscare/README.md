# Handoff: TODOSCARE — Plataforma médica/odontológica (PWA)

## Overview
TODOSCARE es una plataforma de salud/bienestar multi-tenant (SaaS) con foco mobile-first (PWA en React Native / webview de WhatsApp o Chrome — **no** app nativa de las tiendas). Cubre onboarding de pacientes, agenda de especialidades, telemedicina, laboratorio, farmacia, billetera con gamificación, asistente por WhatsApp/IA, y portales de gestión (empresa, administrador, CRM financiero y aseguradoras/prestadores).

Este bundle contiene: (1) un **prototipo interactivo** de la app del paciente y los portales, y (2) **especificaciones funcionales** por rol que detallan datos, permisos (RBAC), pantallas, flujos, estados, integraciones y cumplimiento legal.

## About the Design Files
Los archivos de este bundle son **referencias de diseño creadas en HTML** — prototipos que muestran el look & feel y el comportamiento previsto, **no** código de producción para copiar tal cual. La tarea es **recrear estos diseños en el entorno del proyecto**: el stack ya definido es **backend Python + FastAPI + PostgreSQL (SQLAlchemy async)** y **frontend React + Vite + TypeScript + Tailwind (PWA)**. Implementar con los patrones y librerías de ese stack, no incrustar el HTML.

Los archivos `.dc.html` son "Design Components": HTML que abre en el navegador. Los prototipos usan React vía un runtime propio (`support.js`) — sirven como referencia visual y de interacción, no como componentes a importar.

## Fidelity
- **Prototipo de la app (paciente + portales): hi-fi.** Colores, tipografía, espaciado e interacciones son definitivos — recrear pixel-perfect con las librerías del codebase. Es un prototipo de UX, con datos de ejemplo (mock); la lógica real (persistencia, auth, pagos) debe implementarse contra el backend.
- **Documentos de especificación: contenido funcional hi-fi.** Su estilo (documento impreso) es solo presentación; lo relevante es el contenido: modelo de datos, RBAC, flujos e integraciones.

## Design Tokens
Paleta y tipografía usadas en el prototipo (recrear como tokens Tailwind / CSS vars):

**Colores**
- Teal primario `#0E7C6B` — acciones, marca, activos
- Teal oscuro `#0A5D50` — degradados, texto sobre tinte, estados pressed
- Teal suave `#E4F2EF` — fondos de íconos, chips, selección
- Fondo app `#F4F7F6`
- Tinta / texto `#0F2A24`; texto secundario `#5C6F6A`; sutil `#8A9A96`
- Bordes `#ECF1EF` / `#E7EDEB`
- Acento azul (aseguradoras) `#EAF1FF`; ámbar (pendiente) `#B98900` / fondo `#FBF3E4`; rojo (rechazo) `#C86B5E` / fondo `#F9E5E1`
- WhatsApp: header `#075E54`, fondo chat `#EFE7DD`, burbuja usuario `#D9FDD3`

**Tipografía**
- Títulos/UI: **Manrope** (500–800)
- Cuerpo: **Inter** (400–700)
- Tamaños prototipo: títulos de pantalla 21–22px/800; secciones 13px/700; cuerpo 13–14.5px; meta 11–12px
- Mínimo hit target móvil: 44px

**Forma**
- Radios: tarjetas 16px, botones 14px, chips/pills 20px, íconos 10–12px
- Botones: primario (teal sólido), ghost (teal suave), outline (blanco + borde)
- Barra de tabs inferior con blur; degradado de marca `linear-gradient(135deg, #0E7C6B, #0A5D50)`

## Screens / Views (prototipo)
Seis "teléfonos" (390px de ancho, marco iOS) más los portales. Cada uno es un flujo:

1. **Registro + T&C** — 5 campos obligatorios (Nombre, RUT/ID, Teléfono, Dirección, Correo) + aceptación de T&C en modal (bloqueante, re-aceptación por versión). CTA "Crear cuenta" deshabilitado hasta aceptar.
2. **Onboarding** — 5 preguntas de salud (una pantalla c/u, opción única con check) + paso de dependientes (agregar/quitar, omitir). Pantalla de éxito con nivel Plata. Indicador de progreso por puntos.
3. **App principal** (tabs: Inicio, Agenda, Salud, Farmacia, Perfil):
   - *Inicio*: saludo, tarjeta de nivel/puntos, 6 acciones rápidas (Agendar, Telemedicina, Laboratorio, Farmacia, Imágenes, Dental), bloque asistente WhatsApp, promociones (carrusel).
   - *Agenda*: lista de especialidades (ícono/duración/precio) → horarios (grid, cercanía por geo) → confirmación. Botón atrás en cada paso.
   - *Salud*: menú de 6 → Mi ficha clínica, Resultados de exámenes (+odontograma), Ficha dental (odontograma+tratamientos), Agendamientos realizados, Hospitalizaciones, Subir info (foto/PDF→IA), **QR de emergencia** (SVG, datos críticos, acceso solo lectura auditado).
   - *Farmacia*: medicamentos recetados, pedir por WhatsApp, farmacia cercana.
   - *Perfil*: tarjeta billetera (abre detalle), progreso de niveles (Bronce/Plata/Oro/Diamante con barra), datos personales enmascarados.
   - *Billetera* (desde Perfil): puntos + cashback, pagar con cashback / canjear puntos, historial de movimientos.
4. **Bot WhatsApp** — chat: pide resultado de examen (entrega PDF + correo); pregunta cómo agendar → bot entrega link que abre guía de 4 pasos haciendo el agendamiento real (paso a paso guiado).
5. **Portal Empresa/Cliente** — KPIs (citas hoy, ingresos), Configurar agendas, Productos y servicios + precios, Promociones, Información de la empresa. Cada sección abre su detalle.
6. **Portal Administrador** — acceso total: Clínicas y sucursales, Usuarios y roles, Configuración global (planes, T&C, integraciones), Finanzas (ledger, split).
7. **CRM · Gestión de clínicas** — panel consolidado + lista por clínica (ingresos, margen ▲/▼, pacientes) → detalle con KPIs, ocupación de agenda, ingresos por servicio.
8. **Login Aseguradoras/Prestadores** — KPIs (afiliados, atenciones, por liquidar, autorizaciones), Convenios/coberturas, Autorizaciones (aprobada/pendiente/rechazada), Liquidaciones por clínica.

## Interactions & Behavior
- Navegación por tabs (estado `tab`), sub-vistas con back (`agendaStep`, `saludView`, `empresaView`, `adminView`, `partnerView`, `crmClinic`, `walletOpen`, `waStep`).
- Transiciones suaves (fadeUp/popIn ~0.3–0.4s). Estados hover/pressed en botones (scale 0.97).
- Guía paso a paso: el bot devuelve un enlace que abre la pantalla real en modo asistido (no un tutorial estático).
- Estados de UI a implementar en todas las pantallas: vacío, cargando (skeletons), error (mensaje + reintento), éxito, offline (PWA, solo lectura). Detallado por rol en las specs.

## State Management
El prototipo usa estado local de ejemplo. En producción, cada spec define el modelo de datos y las transiciones. Requisitos transversales:
- **Auth + RBAC contextual**: rol vinculado a clínica/sucursal (clinic_id) — ver specs.
- **Aislamiento multi-tenant**: toda query valida clinic_id; nunca cruzar datos entre tenants.
- **Data fetching**: agenda (anti doble-reserva), ficha clínica (JSONB), ledger financiero (inmutable), integraciones externas (WhatsApp/IA, lab, farmacia, pago/split, aseguradoras, mapas, web push).

## Roles y specs (leer en este orden)
Cada `specs/Spec *.dc.html` contiene: resumen, modelo de datos, matriz RBAC (Ver/Crear/Editar/Eliminar), pantallas, flujos paso a paso con errores, estados de UI, notificaciones, integraciones, cumplimiento legal (Chile/Brasil/Colombia/México) y preguntas abiertas por definir.

1. **Spec Paciente** — usuario final.
2. **Spec Administrador** — acceso total, multi-tenant, planes (incl. sistema público federal/estatal/municipal).
3. **Spec Empresa Cliente** — clínica prestadora y empresa B2B.
4. **Spec Medico** — único rol con acceso al dato clínico; prontuario, prescripción, órdenes.
5. **Spec CRM Clinicas** — indicadores financieros con fórmulas y conectores.
6. **Spec Aseguradora Prestador** — convenios, autorizaciones, liquidaciones.

## Assets
- `prototypes/ios-frame.jsx`, `prototypes/support.js` — runtime/marcos del prototipo (referencia; no portar).
- Iconografía: emoji en el prototipo como placeholder — reemplazar por un set de íconos del codebase (p. ej. Phosphor/Lucide) en producción.
- No hay imágenes de marca reales; usar los assets del proyecto cuando existan.

## Files
- `prototypes/TODOSCARE App Prototype.dc.html` — fuente editable del prototipo (Design Component).
- `prototypes/TODOSCARE App Prototype (standalone).html` — versión autónoma, abre offline en cualquier navegador (la más fácil de revisar).
- `specs/Spec *.dc.html` — 6 documentos de especificación por rol (imprimibles a PDF).
- `specs/doc-page.js` — runtime de los documentos (no portar).

## Backend ya iniciado (contexto)
El equipo ya tiene una base de backend: PostgreSQL 13+ (pgcrypto, btree_gist), FastAPI async, SQLAlchemy async, JWT + bcrypt. Tablas por fases: núcleo (clinics/branches/users/patients + RBAC contextual), clínico (agenda anti-conflicto GiST, prontuario JSONB, odontograma, prescripciones), operacional (estoque, centros de costo, órdenes de lab), CRM/IA (portal paciente, ingesta de exámenes human-in-the-loop), financiero (ledger inmutable, convenios/aranceles, split de pagos). Las specs de este bundle deben mapearse sobre ese esquema.
