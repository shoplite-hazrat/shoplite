const product = {
  type: 'object',
  properties: {
    id: { type: 'string', format: 'uuid' },
    sku: { type: 'string' },
    name: { type: 'string' },
    description: { type: 'string' },
    priceCents: { type: 'integer' },
    stock: { type: 'integer' },
    createdAt: { type: 'string', format: 'date-time' },
    updatedAt: { type: 'string', format: 'date-time' },
  },
};

const idParams = {
  type: 'object',
  required: ['id'],
  properties: { id: { type: 'string', format: 'uuid' } },
};

export default async function productRoutes(app, { repo, cache }) {
  app.get('/products', {
    schema: {
      querystring: {
        type: 'object',
        properties: {
          limit: { type: 'integer', minimum: 1, maximum: 100, default: 20 },
          offset: { type: 'integer', minimum: 0, default: 0 },
        },
        additionalProperties: false,
      },
      response: { 200: { type: 'object', properties: { items: { type: 'array', items: product } } } },
    },
  }, async (request) => {
    const items = await repo.list(request.query);
    return { items };
  });

  app.get('/products/:id', {
    schema: { params: idParams, response: { 200: product } },
  }, async (request, reply) => {
    const { id } = request.params;
    const cached = await cache.get(id);
    if (cached) {
      reply.header('x-cache', 'hit');
      return cached;
    }
    const found = await repo.getById(id);
    if (!found) return reply.notFound(`product ${id} not found`);
    await cache.set(found);
    reply.header('x-cache', 'miss');
    return found;
  });

  app.post('/products', {
    schema: {
      body: {
        type: 'object',
        required: ['sku', 'name', 'priceCents', 'stock'],
        additionalProperties: false,
        properties: {
          sku: { type: 'string', minLength: 1, maxLength: 64 },
          name: { type: 'string', minLength: 1, maxLength: 200 },
          description: { type: 'string', maxLength: 2000 },
          priceCents: { type: 'integer', minimum: 0 },
          stock: { type: 'integer', minimum: 0 },
        },
      },
      response: { 201: product },
    },
  }, async (request, reply) => {
    const result = await repo.create(request.body);
    if (result.status === 'duplicate_sku') {
      return reply.conflict(`sku ${request.body.sku} already exists`);
    }
    return reply.code(201).header('location', `/v1/products/${result.product.id}`).send(result.product);
  });

  // Called by order-service. Idempotent per orderId, so it is safe to retry.
  app.post('/products/:id/reserve', {
    schema: {
      params: idParams,
      body: {
        type: 'object',
        required: ['orderId', 'quantity'],
        additionalProperties: false,
        properties: {
          orderId: { type: 'string', format: 'uuid' },
          quantity: { type: 'integer', minimum: 1, maximum: 1000 },
        },
      },
      response: { 200: product },
    },
  }, async (request, reply) => {
    const { id } = request.params;
    const result = await repo.reserve({ productId: id, ...request.body });
    switch (result.status) {
      case 'not_found':
        return reply.notFound(`product ${id} not found`);
      case 'insufficient_stock':
        return reply.conflict(`insufficient stock for product ${id}`);
      case 'reserved':
        await cache.invalidate(id);
        return result.product;
      case 'already_reserved':
        return result.product;
      default:
        throw new Error(`unexpected reserve status ${result.status}`);
    }
  });
}
