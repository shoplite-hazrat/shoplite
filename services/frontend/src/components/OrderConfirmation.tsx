import { formatPrice } from '../cart';
import type { Order } from '../types';

interface Props {
  order: Order;
  onContinue: () => void;
}

export function OrderConfirmation({ order, onContinue }: Props) {
  return (
    <section className="confirmation" aria-labelledby="confirmation-title">
      <h2 id="confirmation-title">Thank you! Your order is confirmed.</h2>
      <p className="muted">
        A confirmation email is on its way to <strong>{order.customerEmail}</strong>.
      </p>
      <ul className="cart-lines">
        {order.items.map((item) => (
          <li key={item.productId}>
            <span className="cart-name">
              {item.quantity} × {item.productName}
            </span>
            <span className="line-total">{formatPrice(item.unitPriceCents * item.quantity)}</span>
          </li>
        ))}
      </ul>
      <div className="cart-total">
        <span>Total paid</span>
        <strong data-testid="order-total">{formatPrice(order.totalCents)}</strong>
      </div>
      <p className="muted small">Order id: {order.id}</p>
      <button type="button" className="primary" onClick={onContinue}>
        Continue shopping
      </button>
    </section>
  );
}
