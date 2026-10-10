// All configuration comes from environment variables (12-factor).
// Fail fast at startup if something required is missing.

function int(name, fallback) {
  const raw = process.env[name];
  if (raw === undefined || raw === '') return fallback;
  const value = Number.parseInt(raw, 10);
  if (Number.isNaN(value)) throw new Error(`${name} must be an integer, got "${raw}"`);
  return value;
}

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing required environment variable ${name}`);
  return value;
}

export function loadConfig() {
  return {
    port: int('PORT', 3000),
    host: process.env.HOST ?? '0.0.0.0',
    logLevel: process.env.LOG_LEVEL ?? 'info',
    databaseUrl: required('DATABASE_URL'),
    dbPoolMax: int('DB_POOL_MAX', 10),
    // Redis is optional: without it the service runs uncached.
    redisUrl: process.env.REDIS_URL || null,
    cacheTtlSeconds: int('CACHE_TTL_SECONDS', 60),
    // How long to wait for in-flight requests on SIGTERM before forcing exit.
    shutdownTimeoutMs: int('SHUTDOWN_TIMEOUT_MS', 10_000),
  };
}
