import { useCallback, useEffect, useReducer, useState } from 'react';
import { ApiError, listProducts, orderErrorMessage, placeOrder } from './api';
import { cartCount, cartLines, cartReducer } from './cart';
import { CartPanel } from './components/CartPanel';
import { OrderConfirmation } from './components/OrderConfirmation';
import { ProductList } from './components/ProductList';
import type { Order, Product } from './types';

type Load = { state: 'loading' } | { state: 'error'; message: string } | { state: 'ready' };

export function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [load, setLoad] = useState<Load>({ state: 'loading' });
  const [cart, dispatch] = useReducer(cartReducer, {});
  const [submitting, setSubmitting] = useState(false);
  const [orderError, setOrderError] = useState<string | null>(null);
  const [placed, setPlaced] = useState<Order | null>(null);

  const refresh = useCallback(async () => {
    try {
      const items = await listProducts();
      setProducts(items);
      dispatch({ type: 'syncStock', products: items });
      setLoad({ state: 'ready' });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Could not load products.';
      setLoad({ state: 'error', message });
    }
  }, []);

  useEffect(() => {
    // Initial data load: an external-system sync, which is what effects are for.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
  }, [refresh]);

  async function checkout(email: string) {
    setSubmitting(true);
    setOrderError(null);
    try {
      const order = await placeOrder(
        email,
        cartLines(cart).map((l) => ({ productId: l.product.id, quantity: l.quantity })),
      );
      dispatch({ type: 'clear' });
      setPlaced(order);
    } catch (err) {
      setOrderError(orderErrorMessage(err));
    } finally {
      setSubmitting(false);
      // Stock changed either way (our order, or someone else's that beat us).
      void refresh();
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>ShopLite</h1>
        <span className="badge" aria-label="Items in cart">
          {cartCount(cart)} in cart
        </span>
      </header>

      <main className="layout">
        {placed ? (
          <OrderConfirmation order={placed} onContinue={() => setPlaced(null)} />
        ) : (
          <>
            <section className="catalog">
              {load.state === 'loading' && <p className="muted">Loading products…</p>}
              {load.state === 'error' && (
                <div role="alert" className="error">
                  {load.message}{' '}
                  <button type="button" onClick={() => void refresh()}>
                    Retry
                  </button>
                </div>
              )}
              {load.state === 'ready' && (
                <ProductList
                  products={products}
                  cart={cart}
                  onAdd={(product) => dispatch({ type: 'add', product })}
                />
              )}
            </section>
            <CartPanel
              cart={cart}
              dispatch={dispatch}
              onCheckout={(email) => void checkout(email)}
              submitting={submitting}
              error={orderError}
            />
          </>
        )}
      </main>
    </div>
  );
}
