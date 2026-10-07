# Build context: application/frontend  ->  docker build -f docker/frontend.Dockerfile -t taskboard-frontend:1.0.1 application/frontend
# Stage 1: build the React app with Vite
FROM node:24-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build && npm test
# Stage 2: serve static files with an UNPRIVILEGED nginx (runs as uid 101, listens on 8080, no node_modules)
FROM nginxinc/nginx-unprivileged:alpine
# DevSecOps fix: patch OS packages with known, fixed CVEs (the Trivy gate found HIGH/CRITICAL in the old nginx:1.27-alpine base)
USER root
RUN apk upgrade --no-cache
USER 101
ENV BACKEND_URL=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 8080
