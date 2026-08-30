FROM node:22-slim AS builder
WORKDIR /app
COPY hub/package*.json ./
RUN npm ci
COPY hub/ ./
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY vertex/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
