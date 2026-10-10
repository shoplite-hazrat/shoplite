// Liveness: "is the process healthy?" — never checks dependencies, otherwise a
// database outage would make Kubernetes restart every pod for no benefit.
// Readiness: "can I serve traffic right now?" — checks the database and flips
// to 503 during shutdown so the pod is removed from load balancing first.

export default async function healthRoutes(app, { repo, state }) {
  app.get('/healthz', { logLevel: 'warn' }, async () => ({ status: 'ok' }));

  app.get('/readyz', { logLevel: 'warn' }, async (request, reply) => {
    if (state.shuttingDown) {
      return reply.code(503).send({ status: 'shutting_down' });
    }
    try {
      await repo.ping();
      return { status: 'ready' };
    } catch (err) {
      request.log.warn({ err }, 'readiness check failed');
      return reply.code(503).send({ status: 'database_unavailable' });
    }
  });
}
