# AEGIS Cockpit — Cloud Run container (frontend SPA + Vertex AI inference server)
# Port 8080, single process, no nginx required.

# Stage 1: Build the Vite frontend
# VITE_BRIDGE_URL is intentionally empty so the frontend calls /claude/stream
# on the same origin as the server (same-origin relative fetch).
FROM node:22-alpine AS build-frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN VITE_BRIDGE_URL="" npm run build

# Stage 2: Build the Node.js backend
FROM node:22-alpine AS build-server
WORKDIR /app/server
COPY server/package*.json ./
RUN npm ci
COPY server/ ./
RUN npm run build

# Stage 3: Runtime image
FROM node:22-alpine AS runtime
WORKDIR /app

# Copy production server deps only
COPY server/package*.json ./server/
RUN cd server && npm ci --omit=dev

# Copy built artefacts
COPY --from=build-frontend /app/dist ./dist
COPY --from=build-server   /app/server/dist ./server/dist

EXPOSE 8080

ENV NODE_ENV=production

# GOOGLE_CLOUD_PROJECT — set in Cloud Run env vars to enable Vertex AI.
# If unset the server falls back to ANTHROPIC_API_KEY direct.
CMD ["node", "server/dist/index.js"]
