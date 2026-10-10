// Read-through cache for single products. Cache errors are logged and ignored:
// Redis being down must slow the service down, not take it down.

export function createRedisCache(redis, { ttlSeconds, logger }) {
  const key = (id) => `catalog:product:${id}`;

  return {
    async get(id) {
      try {
        const raw = await redis.get(key(id));
        return raw ? JSON.parse(raw) : null;
      } catch (err) {
        logger.warn({ err }, 'cache get failed');
        return null;
      }
    },
    async set(product) {
      try {
        await redis.set(key(product.id), JSON.stringify(product), 'EX', ttlSeconds);
      } catch (err) {
        logger.warn({ err }, 'cache set failed');
      }
    },
    async invalidate(id) {
      try {
        await redis.del(key(id));
      } catch (err) {
        logger.warn({ err }, 'cache invalidate failed');
      }
    },
  };
}

export const noopCache = {
  async get() {
    return null;
  },
  async set() {},
  async invalidate() {},
};
