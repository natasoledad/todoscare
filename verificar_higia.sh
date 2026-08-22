#!/usr/bin/env bash
# Verificación remota post-deploy de Higia (solo lectura, no toca datos).
# Uso:  bash verificar_higia.sh            (contra https://higia.cl)
#       BASE=https://higia.cl bash verificar_higia.sh
set -u
BASE="${BASE:-https://higia.cl}"
API="$BASE/api"
ok=0; fail=0
G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; N='\033[0m'

check() { # nombre  "condición ya evaluada (0/1)"  detalle
  if [ "$2" = "0" ]; then echo -e "  ${G}[OK]${N}  $1"; ok=$((ok+1))
  else echo -e "  ${R}[FALLA]${N} $1 ${Y}$3${N}"; fail=$((fail+1)); fi
}

echo "▶ Verificando $BASE"
echo

# 1) API viva
body=$(curl -fsS --max-time 15 "$API/health" 2>/dev/null || true)
echo "$body" | grep -q '"status"' && check "API responde (/api/health)" 0 || check "API responde (/api/health)" 1 "respuesta: ${body:-<sin respuesta>}"

# 2) Frontend sirve
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$BASE/" 2>/dev/null || echo 000)
[ "$code" = "200" ] && check "Frontend carga (/) -> 200" 0 || check "Frontend carga (/)" 1 "HTTP $code"

# 3) Router público NUEVO desplegado (agenda online): 404 con detalle propio, no "Not Found" genérico
body=$(curl -s --max-time 15 "$API/public/reservas/__probe_no_existe__" 2>/dev/null || true)
echo "$body" | grep -qi 'cl.nica' && check "Agenda online pública desplegada (/api/public/reservas)" 0 \
  || check "Agenda online pública desplegada" 1 "respuesta: ${body:-<vacío>}"

# 4) Endpoint NUEVO con auth (reportes/BI): sin token debe pedir credenciales (401)
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$API/empresa/reportes/agenda-kpis" 2>/dev/null || echo 000)
{ [ "$code" = "401" ] || [ "$code" = "403" ]; } && check "Reportería/BI desplegada (/api/empresa/reportes) -> $code" 0 \
  || check "Reportería/BI desplegada" 1 "HTTP $code (se esperaba 401/403)"

# 5) HTTPS/certificado válido
curl -fsS --max-time 15 -o /dev/null "$BASE/" 2>/dev/null && check "Certificado HTTPS válido" 0 || check "Certificado HTTPS válido" 1 "curl no validó TLS"

# 6) LOGIN vivo: con credenciales basura el endpoint debe responder 401/422
#    (NO 000/502/404). Esto separa "backend caído / mal ruteado" de "clave mala".
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"__probe__@higia.cl","password":"__no_existe__"}' 2>/dev/null || echo 000)
case "$code" in
  401|422) check "Login responde (POST /api/auth/login) -> $code (endpoint sano)" 0 ;;
  200)     check "Login responde -> 200 (¡ojo! credenciales de prueba aceptadas?)" 1 "revisar" ;;
  000)     check "Login responde" 1 "sin respuesta (backend caído o TLS)" ;;
  *)       check "Login responde (POST /api/auth/login)" 1 "HTTP $code (se esperaba 401/422)" ;;
esac

# 7) Conectores Bloque D (PR-AP): endpoint con auth -> 401/403 sin token
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$API/admin/conectores?clinic_id=00000000-0000-0000-0000-000000000000" 2>/dev/null || echo 000)
{ [ "$code" = "401" ] || [ "$code" = "403" ]; } && check "Conectores Bloque D desplegados (/api/admin/conectores) -> $code" 0 \
  || check "Conectores Bloque D desplegados" 1 "HTTP $code (se esperaba 401/403; 404 = falta deploy)"

# 8) Copago chileno (PR-AQ): endpoint con auth -> 401/403 sin token
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$API/empresa/copago/coberturas" 2>/dev/null || echo 000)
{ [ "$code" = "401" ] || [ "$code" = "403" ]; } && check "Copago (seguros compl. + CCAF) desplegado (/api/empresa/copago) -> $code" 0 \
  || check "Copago (seguros compl. + CCAF) desplegado" 1 "HTTP $code (se esperaba 401/403; 404 = falta deploy)"

echo
if [ "$fail" -eq 0 ]; then echo -e "${G}✅ Todo OK ($ok chequeos).${N}"
else echo -e "${R}✖ $fail chequeo(s) con problema, $ok OK.${N}"; fi
exit "$fail"
