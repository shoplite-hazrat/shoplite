# catalog-service

Product catalog API for ShopLite. Node.js 24, Fastify 5, PostgreSQL, optional Redis cache.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/v1/products?limit=20&offset=0` | List products |
| GET | `/v1/products/:id` | Get one product (Redis-cached, `x-cache: hit\|miss`) |
| POST | `/v1/products` | Create `{sku, name, description?, priceCents, stock}` |
| POST | `/v1/products/:id/reserve` | Reserve stock `{orderId, quantity}`. Idempotent per `orderId`; `409` if stock is insufficient |
| POST | `/v1/products/:id/release` | Undo a reservation `{orderId}` (saga compensation). Idempotent |
| GET | `/healthz` | Liveness. Never checks dependencies |
| GET | `/readyz` | Readiness. Checks Postgres; `503` while shutting down |
| GET | `/metrics` | Prometheus metrics |

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | — (required) | `postgres://user:pass@host:5432/catalog` |
| `REDIS_URL` | unset | Unset or unreachable means no caching, not an outage |
| `PORT` | `3000` | |
| `LOG_LEVEL` | `info` | JSON logs to stdout |
| `DB_POOL_MAX` | `10` | Connections per pod. Multiply by replicas when sizing Postgres |
| `CACHE_TTL_SECONDS` | `60` | |
| `SHUTDOWN_TIMEOUT_MS` | `10000` | Keep below the pod's `terminationGracePeriodSeconds` |

## Develop

```bash
npm ci
npm run lint && npm test
DATABASE_URL=postgres://... npm run migrate
DATABASE_URL=postgres://... npm run dev
```

## Container

```bash
docker build -t shoplite/catalog:dev .
docker run --rm -e DATABASE_URL=... shoplite/catalog:dev src/migrate.js   # migrations (a Job in k8s)
docker run --rm -p 3000:3000 -e DATABASE_URL=... shoplite/catalog:dev     # API
```

The runtime image is distroless and runs as a non-root user, with no shell or package manager.

## Design notes

- **Migrations run separately from the app.** In Kubernetes they run as a Job before rollout, so replicas never race each other to migrate.
- **Reservations are idempotent.** The `reservations` table has a primary key on `(order_id, product_id)`, so when order-service retries after a timeout, stock is not decremented twice.
- **Redis is optional.** Cache errors are logged as warnings and the request falls through to Postgres.
- **Metrics are labelled by route template** (`/v1/products/:id`), never by raw URL, which keeps metric cardinality bounded.
