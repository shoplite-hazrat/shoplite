import type { Product } from './types';

export interface CartLine {
  product: Product;
  quantity: number;
}

export type Cart = Record<string, CartLine>;

export type CartAction =
  | { type: 'add'; product: Product }
  | { type: 'setQuantity'; productId: string; quantity: number }
  | { type: 'remove'; productId: string }
  | { type: 'syncStock'; products: Product[] }
  | { type: 'clear' };

export function cartReducer(cart: Cart, action: CartAction): Cart {
  switch (action.type) {
    case 'add': {
      const current = cart[action.product.id]?.quantity ?? 0;
      if (current >= action.product.stock) return cart;
      return { ...cart, [action.product.id]: { product: action.product, quantity: current + 1 } };
    }
    case 'setQuantity': {
      const line = cart[action.productId];
      if (!line) return cart;
      if (action.quantity <= 0) return cartReducer(cart, { type: 'remove', productId: action.productId });
      const quantity = Math.min(action.quantity, line.product.stock);
      return { ...cart, [action.productId]: { ...line, quantity } };
    }
    case 'remove': {
      const next = { ...cart };
      delete next[action.productId];
      return next;
    }
    case 'syncStock': {
      // After a refresh, drop items that sold out and cap quantities to stock.
      const byId = new Map(action.products.map((p) => [p.id, p]));
      const next: Cart = {};
      for (const [id, line] of Object.entries(cart)) {
        const product = byId.get(id);
        if (!product || product.stock === 0) continue;
        next[id] = { product, quantity: Math.min(line.quantity, product.stock) };
      }
      return next;
    }
    case 'clear':
      return {};
  }
}

export function cartLines(cart: Cart): CartLine[] {
  return Object.values(cart);
}

export function cartTotalCents(cart: Cart): number {
  return cartLines(cart).reduce((sum, l) => sum + l.product.priceCents * l.quantity, 0);
}

export function cartCount(cart: Cart): number {
  return cartLines(cart).reduce((sum, l) => sum + l.quantity, 0);
}

const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

export function formatPrice(cents: number): string {
  return money.format(cents / 100);
}
