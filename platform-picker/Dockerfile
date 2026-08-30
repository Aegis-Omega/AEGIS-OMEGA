# Build context: repo root (docker build -f platform-picker/Dockerfile .)
FROM node:22-alpine AS build
WORKDIR /app
COPY packages/shared ./packages/shared
COPY platform-picker/package*.json ./platform-picker/
RUN cd platform-picker && npm ci
COPY platform-picker/ ./platform-picker/
ARG VITE_DASHSCOPE_API_KEY
ARG VITE_DASHSCOPE_MODEL=qwen-plus
ARG VITE_GRANT_SECRET=aegis-omega-v1
ARG VITE_HUB_URL=https://aegisomega.com
RUN cd platform-picker && npm run build

FROM nginx:alpine
COPY --from=build /app/platform-picker/dist /usr/share/nginx/html
COPY platform-picker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
