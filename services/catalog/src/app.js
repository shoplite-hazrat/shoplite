import { randomUUID } from 'node:crypto';
import Fastify from 'fastify';
import sensible from '@fastify/sensible';
import { noopCache } from './cache.js';
import { registerMetrics } from './metrics.js';
import healthRoutes from './routes/health.js';
import productRoutes from './routes/products.js';

// Builds the HTTP app from its dependencies. No I/O happens here, which keeps
// it fast to construct in tests with fake dependencies.
export function buildApp({ repo, cache = noopCache, logger = true, state = { shuttingDown: false } }) {
  const app = Fastify({
    logger,
    // Propagate the caller's request id (set by the gateway) so one request can
    // be followed across services in the logs.
    requestIdHeader: 'x-request-id',
    genReqId: () => randomUUID(),
  });

  app.register(sensible);
  app.addHook('onSend', async (request, reply) => {
    reply.header('x-request-id', request.id);
  });

  registerMetrics(app);
  app.register(healthRoutes, { repo, state });
  app.register(productRoutes, { prefix: '/v1', repo, cache });

  return app;
}
