// Demo data so a fresh environment has something to show.
const products = [
  ['SL-TSHIRT-001', 'ShopLite T-Shirt', 'Soft cotton tee with the ShopLite logo', 1999, 120],
  ['SL-MUG-001', 'Kubernetes Mug', 'Holds 350ml of coffee, or one pod', 1299, 80],
  ['SL-STICKER-001', 'Sticker Pack', 'Ten stickers for your laptop', 499, 500],
  ['SL-HOODIE-001', 'DevOps Hoodie', 'Warm hoodie for late-night incidents', 4999, 40],
  ['SL-CAP-001', 'Helm Cap', 'Baseball cap with an embroidered helm', 2499, 60],
];

export const up = (pgm) => {
  for (const [sku, name, description, priceCents, stock] of products) {
    pgm.sql(
      `INSERT INTO products (sku, name, description, price_cents, stock)
       VALUES ('${sku}', '${name}', '${description}', ${priceCents}, ${stock})
       ON CONFLICT (sku) DO NOTHING`,
    );
  }
};

export const down = (pgm) => {
  pgm.sql(`DELETE FROM products WHERE sku IN (${products.map(([sku]) => `'${sku}'`).join(', ')})`);
};
