import { describe, expect, it } from 'vitest';
import { cartCount, cartReducer, cartTotalCents, formatPrice, type Cart } from './cart';
import type { Product } from './types';

const mug: Product = { id: 'm', sku: 'MUG', name: 'Mug', description: '', priceCents: 1299, stock: 2 };
const cap: Product = { id: 'c', sku: 'CAP', name: 'Cap', description: '', priceCents: 2499, stock: 5 };

describe('cartReducer', () => {
  it('adds products and totals them', () => {
    let cart: Cart = {};
    cart = cartReducer(cart, { type: 'add', product: mug });
    cart = cartReducer(cart, { type: 'add', product: mug });
    cart = cartReducer(cart, { type: 'add', product: cap });
    expect(cartCount(cart)).toBe(3);
    expect(cartTotalCents(cart)).toBe(2 * 1299 + 2499);
  });

  it('never exceeds available stock', () => {
    let cart: Cart = {};
    for (let i = 0; i < 5; i++) cart = cartReducer(cart, { type: 'add', product: mug });
    expect(cart.m?.quantity).toBe(2);
    cart = cartReducer(cart, { type: 'setQuantity', productId: 'm', quantity: 10 });
    expect(cart.m?.quantity).toBe(2);
  });

  it('removes a line when quantity drops to zero', () => {
    let cart = cartReducer({}, { type: 'add', product: mug });
    cart = cartReducer(cart, { type: 'setQuantity', productId: 'm', quantity: 0 });
    expect(cart).toEqual({});
  });

  it('syncs with fresh stock: drops sold-out items and caps quantities', () => {
    let cart: Cart = {};
    cart = cartReducer(cart, { type: 'add', product: mug });
    cart = cartReducer(cart, { type: 'add', product: mug });
    cart = cartReducer(cart, { type: 'add', product: cap });
    cart = cartReducer(cart, {
      type: 'syncStock',
      products: [
        { ...mug, stock: 1 },
        { ...cap, stock: 0 },
      ],
    });
    expect(cart).toEqual({ m: { product: { ...mug, stock: 1 }, quantity: 1 } });
  });
});

describe('formatPrice', () => {
  it('formats cents as dollars', () => {
    expect(formatPrice(4999)).toBe('$49.99');
  });
});
