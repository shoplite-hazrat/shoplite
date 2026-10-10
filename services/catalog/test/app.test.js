import { randomUUID } from 'node:crypto';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { buildApp } from '../src/app.js';
import { createMemoryRepository } from './memory-repository.js';

function createMemoryCache() {
  const store = new Map();
  return {
    store,
    async get(id) {
      return store.get(id) ?? null;
    },
    async set(p) {
      store.set(p.id, p);
    },
    async invalidate(id) {
      store.delete(id);
    },
  };
}

describe('catalog-service', () => {
  let app;
  let repo;
  let cache;
  let state;
  let mug;

  beforeEach(async () => {
    repo = createMemoryRepository([
      { sku: 'MUG', name: 'Mug', priceCents: 1299, stock: 5 },
      { sku: 'CAP', name: 'Cap', priceCents: 2499, stock: 1 },
    ]);
    cache = createMemoryCache();
    state = { shuttingDown: false };
    app = buildApp({ repo, cache, state, logger: false });
    await app.ready();
    [mug] = (await repo.list({ limit: 10, offset: 0 })).filter((p) => p.sku === 'MUG');
  });

  afterEach(() => app.close());

  describe('health', () => {
    it('liveness is always ok', async () => {
      repo.setHealthy(false);
      const res = await app.inject('/healthz');
      expect(res.statusCode).toBe(200);
    });

    it('readiness reflects the database', async () => {
      expect((await app.inject('/readyz')).statusCode).toBe(200);
      repo.setHealthy(false);
      expect((await app.inject('/readyz')).statusCode).toBe(503);
    });

    it('readiness fails while shutting down', async () => {
      state.shuttingDown = true;
      const res = await app.inject('/readyz');
      expect(res.statusCode).toBe(503);
      expect(res.json().status).toBe('shutting_down');
    });
  });

  describe('GET /v1/products', () => {
    it('lists products sorted by name', async () => {
      const res = await app.inject('/v1/products');
      expect(res.statusCode).toBe(200);
      expect(res.json().items.map((p) => p.sku)).toEqual(['CAP', 'MUG']);
    });

    it('rejects an out-of-range limit', async () => {
      const res = await app.inject('/v1/products?limit=1000');
      expect(res.statusCode).toBe(400);
    });
  });

  describe('GET /v1/products/:id', () => {
    it('returns a product and caches it', async () => {
      const first = await app.inject(`/v1/products/${mug.id}`);
      expect(first.statusCode).toBe(200);
      expect(first.headers['x-cache']).toBe('miss');
      expect(first.json()).toMatchObject({ sku: 'MUG', priceCents: 1299 });

      const second = await app.inject(`/v1/products/${mug.id}`);
      expect(second.headers['x-cache']).toBe('hit');
    });

    it('returns 404 for an unknown id', async () => {
      const res = await app.inject(`/v1/products/${randomUUID()}`);
      expect(res.statusCode).toBe(404);
    });

    it('returns 400 for a malformed id', async () => {
      const res = await app.inject('/v1/products/not-a-uuid');
      expect(res.statusCode).toBe(400);
    });
  });

  describe('POST /v1/products', () => {
    it('creates a product', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/products',
        payload: { sku: 'HAT', name: 'Hat', priceCents: 999, stock: 3 },
      });
      expect(res.statusCode).toBe(201);
      expect(res.headers.location).toBe(`/v1/products/${res.json().id}`);
    });

    it('rejects a duplicate sku', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/products',
        payload: { sku: 'MUG', name: 'Another mug', priceCents: 1, stock: 1 },
      });
      expect(res.statusCode).toBe(409);
    });

    it('rejects a negative price', async () => {
      const res = await app.inject({
        method: 'POST',
        url: '/v1/products',
        payload: { sku: 'BAD', name: 'Bad', priceCents: -1, stock: 1 },
      });
      expect(res.statusCode).toBe(400);
    });
  });

  describe('POST /v1/products/:id/reserve', () => {
    const reserve = (id, body) => app.inject({ method: 'POST', url: `/v1/products/${id}/reserve`, payload: body });

    it('decrements stock and invalidates the cache', async () => {
      await app.inject(`/v1/products/${mug.id}`); // warm the cache
      const res = await reserve(mug.id, { orderId: randomUUID(), quantity: 2 });
      expect(res.statusCode).toBe(200);
      expect(res.json().stock).toBe(3);
      expect(cache.store.has(mug.id)).toBe(false);
    });

    it('is idempotent for the same order', async () => {
      const orderId = randomUUID();
      await reserve(mug.id, { orderId, quantity: 2 });
      const retry = await reserve(mug.id, { orderId, quantity: 2 });
      expect(retry.statusCode).toBe(200);
      expect(retry.json().stock).toBe(3);
    });

    it('returns 409 when stock is insufficient', async () => {
      const res = await reserve(mug.id, { orderId: randomUUID(), quantity: 6 });
      expect(res.statusCode).toBe(409);
    });

    it('returns 404 for an unknown product', async () => {
      const res = await reserve(randomUUID(), { orderId: randomUUID(), quantity: 1 });
      expect(res.statusCode).toBe(404);
    });
  });

  describe('POST /v1/products/:id/release', () => {
    const post = (action, id, body) => app.inject({ method: 'POST', url: `/v1/products/${id}/${action}`, payload: body });

    it('returns reserved stock and is idempotent', async () => {
      const orderId = randomUUID();
      await post('reserve', mug.id, { orderId, quantity: 2 });
      const first = await post('release', mug.id, { orderId });
      expect(first.statusCode).toBe(200);
      expect(first.json().stock).toBe(5);
      const retry = await post('release', mug.id, { orderId });
      expect(retry.statusCode).toBe(200);
      expect(retry.json().stock).toBe(5);
    });

    it('allows the same order to reserve again after release', async () => {
      const orderId = randomUUID();
      await post('reserve', mug.id, { orderId, quantity: 2 });
      await post('release', mug.id, { orderId });
      const again = await post('reserve', mug.id, { orderId, quantity: 1 });
      expect(again.json().stock).toBe(4);
    });

    it('returns 404 for an unknown product', async () => {
      const res = await post('release', randomUUID(), { orderId: randomUUID() });
      expect(res.statusCode).toBe(404);
    });
  });

  describe('observability', () => {
    it('echoes the incoming request id', async () => {
      const res = await app.inject({ url: '/healthz', headers: { 'x-request-id': 'abc-123' } });
      expect(res.headers['x-request-id']).toBe('abc-123');
    });

    it('exposes route-templated request metrics', async () => {
      await app.inject(`/v1/products/${mug.id}`);
      const res = await app.inject('/metrics');
      expect(res.statusCode).toBe(200);
      expect(res.body).toContain('http_request_duration_seconds_count{method="GET",route="/v1/products/:id",status_code="200"} 1');
    });
  });
});
