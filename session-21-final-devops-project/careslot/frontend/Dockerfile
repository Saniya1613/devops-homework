# CareSlot frontend image:  docker build -t careslot-frontend:local ./frontend
# ---- Stage 1: build the React app with Node + Vite ----
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build && npm test

# ---- Stage 2: serve only the static files with an unprivileged nginx (uid 101, port 8080) ----
FROM nginxinc/nginx-unprivileged:alpine
USER root
# patch OS packages so the Trivy gate does not fail on already-fixed CVEs
RUN apk upgrade --no-cache
USER 101
ENV BACKEND_URL=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/nginx-health || exit 1
