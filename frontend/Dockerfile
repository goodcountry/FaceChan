# syntax=docker/dockerfile:1

# ── Base: install dependencies ─────────────────────────────────────────────────
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

# ── Development stage ──────────────────────────────────────────────────────────
# Runs Vite dev server with hot reload on port 5173.
# Used by docker-compose.yml (local dev).
FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# ── Production build ───────────────────────────────────────────────────────────
FROM base AS build
COPY . .
RUN npm run build

# ── Production serve ───────────────────────────────────────────────────────────
# Lightweight Nginx container serving the built React files.
# Used by docker-compose.prod.yml — the main Nginx proxies /* to this container.
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
