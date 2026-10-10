# ShopLite: application monorepo

Source code, tests, Dockerfiles and CI for the ShopLite services.
Deployment config lives in [`shoplite-gitops`](https://github.com/shoplite-hazrat/shoplite-gitops) and cluster infrastructure in [`shoplite-infra`](https://github.com/shoplite-hazrat/shoplite-infra).

## Quick start

Requires Docker with Compose v2.

```bash
make up       # build and start everything, wait until healthy (~2 min first time)
make smoke    # end-to-end test through the gateway
```

| URL | What |
|---|---|
| http://localhost:8080 | The shop (through the gateway) |
| http://localhost:8025 | Mailpit: order confirmation emails land here |

Other targets: `make ps`, `make logs s=order`, `make down`, `make clean` (also deletes data).

## Architecture

```
browser ──> gateway :8080 ──┬─ /            -> frontend      (React, nginx)
                            ├─ /api/catalog -> catalog       (Node, Fastify) ──> Postgres, Redis
                            └─ /api/orders  -> order         (Python, FastAPI) ──> Postgres
                                                 │  reserve/release stock (HTTP, saga)
                                                 │  orders.created (outbox -> NATS JetStream)
                                                 v
                                            notification    (Python worker) ──> Postgres, SMTP (Mailpit)
```

| Service | Stack | Port | Docs |
|---|---|---|---|
| frontend | React 19 + Vite, served by nginx | 8080 | [README](services/frontend/README.md) |
| catalog | Node.js 24, Fastify, PostgreSQL, Redis | 3000 | [README](services/catalog/README.md) |
| order | Python 3.14, FastAPI, PostgreSQL, NATS | 8000 | [README](services/order/README.md) |
| notification | Python 3.14 NATS consumer | 8001 (ops only) | [README](services/notification/README.md) |

The **gateway** (`deploy/compose/gateway/`) is the only public entry point and the security boundary. It exposes only what the browser needs, and keeps internal endpoints (stock reserve/release, product admin, metrics, probes) private. It also assigns the `X-Request-Id` that every service logs. In Kubernetes, the Gateway API takes over this role.

## Conventions

- Commits follow [Conventional Commits](https://www.conventionalcommits.org): `feat(catalog): ...`, `fix(order): ...`, `chore(ci): ...`
- `main` is protected: changes land via squash-merged PR.
- Every service exposes `/healthz` (liveness) and `/readyz` (readiness), plus `/metrics` (Prometheus). Each logs JSON to stdout with the request id and handles SIGTERM gracefully.
- Database per service; schema migrations run as a separate one-shot step before the service starts.
