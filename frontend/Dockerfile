FROM node:22.19.0-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
ARG NPM_CONFIG_STRICT_SSL=true
RUN npm ci
COPY frontend/ .
RUN npm run build
FROM nginxinc/nginx-unprivileged:1.29.1-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
