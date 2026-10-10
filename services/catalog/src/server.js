import pg from 'pg';
import { Redis } from 'ioredis';
import closeWithGrace from 'close-with-grace';
import { loadConfig } from './config.js';
import { buildApp } from './app.js';
import { createPgRepository } from './repository.js';
import { createRedisCache, noopCache } from './cache.js';

const config = loadConfig();

const pool = new pg.Pool({ connectionString: config.databaseUrl, max: config.dbPoolMax });
const redis = config.redisUrl
  ? new Redis(config.redisUrl, { maxRetriesPerRequest: 1, enableOfflineQueue: false })
  : null;

// The cache logs through the app's logger, which only exists after buildApp().
const cacheLogger = { warn: (...args) => app.log.warn(...args) };
const cache = redis
  ? createRedisCache(redis, { ttlSeconds: config.cacheTtlSeconds, logger: cacheLogger })
  : noopCache;

const state = { shuttingDown: false };
const app = buildApp({
  repo: createPgRepository(pool),
  cache,
  state,
  logger: {
    level: config.logLevel,
    redact: ['req.headers.authorization', 'req.headers.cookie'],
  },
});

// ioredis reconnects on its own; just make the errors visible.
redis?.on('error', (err) => app.log.warn({ err }, 'redis error'));

pool.on('error', (err) => app.log.error({ err }, 'idle postgres client error'));

// On SIGTERM (what Kubernetes sends): fail readiness, stop accepting new
// connections, let in-flight requests finish, then close dependencies.
closeWithGrace({ delay: config.shutdownTimeoutMs }, async ({ signal, err }) => {
  if (err) app.log.error({ err }, 'shutting down after fatal error');
  else app.log.info({ signal }, 'shutting down');
  state.shuttingDown = true;
  await app.close();
  await pool.end();
  if (redis) await redis.quit().catch(() => {});
});

try {
  await app.listen({ port: config.port, host: config.host });
} catch (err) {
  app.log.error({ err }, 'failed to start');
  process.exit(1);
}
