# ShopLite — application monorepo

Source code, tests, Dockerfiles and CI for the ShopLite services.
Deployment config lives in `shoplite-gitops`; cluster infra in `shoplite-infra`.

| Service | Stack | Port |
|---|---|---|
| frontend | React (Vite) + nginx | 8080 |
| catalog | Node.js (Fastify) + PostgreSQL + Redis | 3000 |
| order | Python (FastAPI) + PostgreSQL + NATS | 8000 |
| notification | Python NATS consumer | 8001 (metrics/health) |

## Conventions
- Commits follow [Conventional Commits](https://www.conventionalcommits.org): `feat(catalog): ...`, `fix(order): ...`, `chore(ci): ...`
- `main` is protected: changes land via PR with green CI.
- Every service exposes `/healthz`, `/readyz`, `/metrics`, logs JSON to stdout, and handles SIGTERM gracefully.
