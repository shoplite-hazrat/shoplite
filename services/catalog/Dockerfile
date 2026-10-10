# syntax=docker/dockerfile:1

# ---- deps: production dependencies only, installed from the lockfile ----
FROM node:25-trixie-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev --ignore-scripts

# ---- runtime: distroless = no shell, no package manager, tiny attack surface ----
FROM gcr.io/distroless/nodejs24-debian13:nonroot
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY package.json ./
COPY src ./src
COPY migrations ./migrations

# nonroot user (uid 65532) is the image default; stated explicitly for clarity.
USER 65532:65532
EXPOSE 3000

# The distroless entrypoint is `node`; run migrations with: ["src/migrate.js"]
CMD ["src/server.js"]
