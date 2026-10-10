# frontend

ShopLite storefront: React 19 + TypeScript + Vite, served as static files by unprivileged nginx.

Browse products, add them to a cart (capped at available stock), and place an order with your email. A confirmation email then arrives through notification-worker.

## How it talks to the backend

The app calls **relative** URLs and never contains backend hostnames:

| Browser calls | Routed to |
|---|---|
| `/api/catalog/v1/...` | catalog-service `/v1/...` |
| `/api/orders/v1/...` | order-service `/v1/...` |

Something in front of the app does that routing:

| Environment | Router |
|---|---|
| `npm run dev` | Vite dev-server proxy (`vite.config.ts`) |
| docker-compose | gateway container |
| Kubernetes | Gateway API (`HTTPRoute`s) |

So one image runs unchanged in every environment, the browser only ever talks to one origin (no CORS), and the backends aren't exposed directly.

## The nginx container

- **Non-root.** `nginx-unprivileged` runs as uid 101 on port 8080.
- **Caching.** `/assets/*` filenames are content-hashed, so they are cached for a year (`immutable`). `index.html` is `no-cache`, so a deploy is picked up on the next page load.
- **SPA fallback.** Unknown paths serve `index.html`. Missing assets are still 404.
- **Security headers** (CSP, `X-Frame-Options`, `nosniff`, and others) are in `nginx/security-headers.conf`, included per `location`. nginx drops inherited `add_header`s in any location that sets its own, a classic way to lose security headers silently.
- **JSON access logs** with the `x-request-id` set by the gateway. `/healthz` is for probes and is not logged.

## Develop

```bash
npm ci
npm run dev          # http://localhost:5173, proxies to catalog :3000 and order :8000
npm run lint && npm run typecheck && npm test
npm run build        # dist/
```

## Container

```bash
docker build -t shoplite/frontend:dev .
docker run --rm -p 8080:8080 shoplite/frontend:dev
```
