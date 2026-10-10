// Data access for products. The rest of the app only talks to this interface,
// which lets tests swap in an in-memory implementation.

const COLUMNS = 'id, sku, name, description, price_cents, stock, created_at, updated_at';

function toProduct(row) {
  return {
    id: row.id,
    sku: row.sku,
    name: row.name,
    description: row.description,
    priceCents: row.price_cents,
    stock: row.stock,
    createdAt: row.created_at.toISOString(),
    updatedAt: row.updated_at.toISOString(),
  };
}

export function createPgRepository(pool) {
  return {
    async ping() {
      await pool.query('SELECT 1');
    },

    async list({ limit, offset }) {
      const { rows } = await pool.query(
        `SELECT ${COLUMNS} FROM products ORDER BY name LIMIT $1 OFFSET $2`,
        [limit, offset],
      );
      return rows.map(toProduct);
    },

    async getById(id) {
      const { rows } = await pool.query(`SELECT ${COLUMNS} FROM products WHERE id = $1`, [id]);
      return rows[0] ? toProduct(rows[0]) : null;
    },

    async create({ sku, name, description, priceCents, stock }) {
      try {
        const { rows } = await pool.query(
          `INSERT INTO products (sku, name, description, price_cents, stock)
           VALUES ($1, $2, $3, $4, $5) RETURNING ${COLUMNS}`,
          [sku, name, description ?? '', priceCents, stock],
        );
        return { status: 'created', product: toProduct(rows[0]) };
      } catch (err) {
        if (err.code === '23505') return { status: 'duplicate_sku' }; // unique_violation
        throw err;
      }
    },

    // Atomically decrement stock for an order. Idempotent per (orderId, productId):
    // a retried request returns 'already_reserved' instead of reserving twice.
    async reserve({ productId, orderId, quantity }) {
      const client = await pool.connect();
      try {
        await client.query('BEGIN');
        const inserted = await client.query(
          `INSERT INTO reservations (order_id, product_id, quantity) VALUES ($1, $2, $3)
           ON CONFLICT (order_id, product_id) DO NOTHING`,
          [orderId, productId, quantity],
        ).catch((err) => {
          if (err.code === '23503') return null; // foreign_key_violation: product missing
          throw err;
        });

        if (inserted === null) {
          await client.query('ROLLBACK');
          return { status: 'not_found' };
        }

        if (inserted.rowCount === 0) {
          await client.query('ROLLBACK');
          const { rows } = await client.query(`SELECT ${COLUMNS} FROM products WHERE id = $1`, [productId]);
          return { status: 'already_reserved', product: toProduct(rows[0]) };
        }

        const updated = await client.query(
          `UPDATE products SET stock = stock - $2, updated_at = now()
           WHERE id = $1 AND stock >= $2 RETURNING ${COLUMNS}`,
          [productId, quantity],
        );
        if (updated.rowCount === 0) {
          await client.query('ROLLBACK');
          return { status: 'insufficient_stock' };
        }

        await client.query('COMMIT');
        return { status: 'reserved', product: toProduct(updated.rows[0]) };
      } catch (err) {
        await client.query('ROLLBACK').catch(() => {});
        throw err;
      } finally {
        client.release();
      }
    },
  };
}
