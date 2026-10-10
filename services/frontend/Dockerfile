# syntax=docker/dockerfile:1

# ---- build: typecheck and bundle the SPA ----
FROM node:24-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --ignore-scripts
COPY . .
RUN npm run build

# ---- runtime: static files only, served by nginx as a non-root user ----
# nginx-unprivileged runs as uid 101 and listens on 8080 (no root needed for <1024).
FROM nginxinc/nginx-unprivileged:1.30-alpine
# Stopgap: pull OS security fixes the base image hasn't shipped yet (CI's Trivy
# gate flagged libtiff). Remove once Dependabot bumps the base past it.
USER root
RUN apk upgrade --no-cache tiff
USER 101
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
