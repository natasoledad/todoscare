#!/usr/bin/env bash
# Despliegue de TODOSCARE en el servidor: trae los últimos cambios de GitHub,
# reconstruye las imágenes y levanta los servicios. Las migraciones de base de
# datos se aplican solas al arrancar la API (sin perder datos).
#
# Uso (en el servidor, dentro de ~/todoscare):   ./deploy.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "▶ 1/3  Trayendo cambios desde GitHub…"
git pull origin main

echo "▶ 2/3  Reconstruyendo y levantando (puede tardar unos minutos)…"
docker compose -f docker-compose.prod.yml up -d --build

echo "▶ 3/3  Estado de los servicios:"
docker compose -f docker-compose.prod.yml ps

echo
echo "✅ Despliegue terminado."
echo "   Verifica la salud:  https://higia.cl/api/health   → {\"status\":\"ok\"}"
echo "   Abre la app:        https://higia.cl"
