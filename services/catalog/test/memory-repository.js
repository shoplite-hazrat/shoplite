import { randomUUID } from 'node:crypto';

// In-memory stand-in for the Postgres repository, with the same behaviour.
export function createMemoryRepository(seed = []) {
  const products = new Map();
  const reservations = new Set();
  let healthy = true;

  for (const p of seed) {
    const now = new Date().toISOString();
    const product = { id: randomUUID(), description: '', createdAt: now, updatedAt: now, ...p };
    products.set(product.id, product);
  }

  return {
    setHealthy(value) {
      healthy = value;
    },
    async ping() {
      if (!healthy) throw new Error('database down');
    },
    async list({ limit, offset }) {
      return [...products.values()]
        .sort((a, b) => a.name.localeCompare(b.name))
        .slice(offset, offset + limit);
    },
    async getById(id) {
      return products.get(id) ?? null;
    },
    async create(data) {
      if ([...products.values()].some((p) => p.sku === data.sku)) return { status: 'duplicate_sku' };
      const now = new Date().toISOString();
      const product = { id: randomUUID(), description: '', ...data, createdAt: now, updatedAt: now };
      products.set(product.id, product);
      return { status: 'created', product };
    },
    async reserve({ productId, orderId, quantity }) {
      const product = products.get(productId);
      if (!product) return { status: 'not_found' };
      const key = `${orderId}:${productId}`;
      if (reservations.has(key)) return { status: 'already_reserved', product };
      if (product.stock < quantity) return { status: 'insufficient_stock' };
      reservations.add(key);
      product.stock -= quantity;
      return { status: 'reserved', product };
    },
  };
}
