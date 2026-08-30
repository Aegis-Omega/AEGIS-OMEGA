FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_GRANT_SECRET
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ARG VITE_LS_LINK_SINGLE
ARG VITE_LS_LINK_STARTER
ARG VITE_LS_LINK_FULL
ARG VITE_URL_PLATFORM_PICKER=https://platform.aegisomega.com
ARG VITE_URL_HOOK_GENERATOR=https://hooks.aegisomega.com
ARG VITE_URL_CONTENT_CALENDAR=https://calendar.aegisomega.com
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
