# AEGIS Studio — constitutional observability layer
# Projection only. No constitutional authority.
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_BRIDGE_URL=/api/bridge
ENV VITE_BRIDGE_URL=$VITE_BRIDGE_URL
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
