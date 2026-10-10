import client from 'prom-client';

// RED metrics (Rate, Errors, Duration) for every route, plus Node.js runtime metrics.
// A registry per app instance keeps tests isolated from each other.
export function registerMetrics(app) {
  const registry = new client.Registry();
  client.collectDefaultMetrics({ register: registry });

  const httpDuration = new client.Histogram({
    name: 'http_request_duration_seconds',
    help: 'HTTP request duration in seconds',
    labelNames: ['method', 'route', 'status_code'],
    buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
    registers: [registry],
  });

  app.addHook('onResponse', async (request, reply) => {
    // Use the route template (/v1/products/:id), never the raw URL,
    // otherwise every product id becomes a new time series.
    const route = request.routeOptions.url ?? 'unmatched';
    if (route === '/metrics') return;
    httpDuration.observe(
      { method: request.method, route, status_code: reply.statusCode },
      reply.elapsedTime / 1000,
    );
  });

  app.get('/metrics', { logLevel: 'warn' }, async (request, reply) => {
    reply.type(registry.contentType);
    return registry.metrics();
  });
}
