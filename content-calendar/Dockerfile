# Build context: repo root (docker build -f content-calendar/Dockerfile .)
FROM node:22-alpine AS build
WORKDIR /app
COPY packages/shared ./packages/shared
COPY content-calendar/package*.json ./content-calendar/
RUN cd content-calendar && npm ci
COPY content-calendar/ ./content-calendar/
ARG VITE_DASHSCOPE_API_KEY
ARG VITE_DASHSCOPE_MODEL=qwen-plus
ARG VITE_GRANT_SECRET=aegis-omega-v1
ARG VITE_HUB_URL=https://aegisomega.com
RUN cd content-calendar && npm run build

FROM nginx:alpine
COPY --from=build /app/content-calendar/dist /usr/share/nginx/html
COPY content-calendar/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
