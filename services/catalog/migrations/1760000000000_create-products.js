export const up = (pgm) => {
  pgm.createTable('products', {
    id: { type: 'uuid', primaryKey: true, default: pgm.func('gen_random_uuid()') },
    sku: { type: 'text', notNull: true, unique: true },
    name: { type: 'text', notNull: true },
    description: { type: 'text', notNull: true, default: '' },
    price_cents: { type: 'integer', notNull: true, check: 'price_cents >= 0' },
    stock: { type: 'integer', notNull: true, check: 'stock >= 0' },
    created_at: { type: 'timestamptz', notNull: true, default: pgm.func('now()') },
    updated_at: { type: 'timestamptz', notNull: true, default: pgm.func('now()') },
  });
  pgm.createIndex('products', 'name');

  // One row per (order, product) makes stock reservation idempotent.
  pgm.createTable('reservations', {
    order_id: { type: 'uuid', notNull: true },
    product_id: { type: 'uuid', notNull: true, references: 'products', onDelete: 'CASCADE' },
    quantity: { type: 'integer', notNull: true, check: 'quantity > 0' },
    created_at: { type: 'timestamptz', notNull: true, default: pgm.func('now()') },
  });
  pgm.addConstraint('reservations', 'reservations_pkey', { primaryKey: ['order_id', 'product_id'] });
};

export const down = (pgm) => {
  pgm.dropTable('reservations');
  pgm.dropTable('products');
};
