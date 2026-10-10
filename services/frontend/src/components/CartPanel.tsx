import { type FormEvent, useState } from 'react';
import type { Cart, CartAction } from '../cart';
import { cartLines, cartTotalCents, formatPrice } from '../cart';

interface Props {
  cart: Cart;
  dispatch: (action: CartAction) => void;
  onCheckout: (email: string) => void;
  submitting: boolean;
  error: string | null;
}

export function CartPanel({ cart, dispatch, onCheckout, submitting, error }: Props) {
  const [email, setEmail] = useState('');
  const lines = cartLines(cart);

  function submit(event: FormEvent) {
    event.preventDefault();
    onCheckout(email.trim());
  }

  return (
    <aside className="cart" aria-label="Cart">
      <h2>Your cart</h2>
      {lines.length === 0 ? (
        <p className="muted">Your cart is empty.</p>
      ) : (
        <>
          <ul className="cart-lines">
            {lines.map(({ product, quantity }) => (
              <li key={product.id}>
                <span className="cart-name">{product.name}</span>
                <span className="qty">
                  <button
                    type="button"
                    className="icon"
                    aria-label={`Decrease ${product.name}`}
                    onClick={() =>
                      dispatch({ type: 'setQuantity', productId: product.id, quantity: quantity - 1 })
                    }
                  >
                    −
                  </button>
                  <span aria-label={`${product.name} quantity`}>{quantity}</span>
                  <button
                    type="button"
                    className="icon"
                    aria-label={`Increase ${product.name}`}
                    disabled={quantity >= product.stock}
                    onClick={() =>
                      dispatch({ type: 'setQuantity', productId: product.id, quantity: quantity + 1 })
                    }
                  >
                    +
                  </button>
                </span>
                <span className="line-total">{formatPrice(product.priceCents * quantity)}</span>
              </li>
            ))}
          </ul>
          <div className="cart-total">
            <span>Total</span>
            <strong data-testid="cart-total">{formatPrice(cartTotalCents(cart))}</strong>
          </div>
          <form onSubmit={submit} className="checkout">
            <label htmlFor="email">Email for your confirmation</label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <button type="submit" className="primary" disabled={submitting}>
              {submitting ? 'Placing order…' : 'Place order'}
            </button>
          </form>
        </>
      )}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </aside>
  );
}
