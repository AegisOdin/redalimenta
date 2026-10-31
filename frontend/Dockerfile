FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.31.7-alpine
# Tratamiento de hallazgos: parches de Alpine y eliminación de curl (no se usa en ejecución)
USER root
RUN apk upgrade --no-cache && apk del --no-cache curl 2>/dev/null || true
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY snippets /etc/nginx/snippets
COPY --from=build /app/dist /usr/share/nginx/html
USER 101
EXPOSE 8080
