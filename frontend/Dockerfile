# ─────────────────────── build stage ───────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# ─────────────────────── runtime stage (nginx) ───────────────────────
FROM nginx:1.27-alpine AS runtime

# Config con fallback SPA + proxy de la API al backend.
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
# nginx corre en foreground por defecto en la imagen oficial.
