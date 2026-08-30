# Build context: repo root (docker build -f hook-generator/Dockerfile .)
FROM node:22-alpine AS build
WORKDIR /app
COPY packages/shared ./packages/shared
COPY hook-generator/package*.json ./hook-generator/
RUN cd hook-generator && npm ci
COPY hook-generator/ ./hook-generator/
ARG VITE_DASHSCOPE_API_KEY
ARG VITE_DASHSCOPE_MODEL=qwen-plus
ARG VITE_GRANT_SECRET=aegis-omega-v1
ARG VITE_HUB_URL=https://aegisomega.com
RUN cd hook-generator && npm run build

FROM nginx:alpine
COPY --from=build /app/hook-generator/dist /usr/share/nginx/html
COPY hook-generator/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
