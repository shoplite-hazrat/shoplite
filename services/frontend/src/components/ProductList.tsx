import type { Cart } from '../cart';
import { formatPrice } from '../cart';
import type { Product } from '../types';

interface Props {
  products: Product[];
  cart: Cart;
  onAdd: (product: Product) => void;
}

export function ProductList({ products, cart, onAdd }: Props) {
  return (
    <ul className="products" aria-label="Products">
      {products.map((product) => {
        const inCart = cart[product.id]?.quantity ?? 0;
        const soldOut = product.stock === 0;
        const maxed = inCart >= product.stock;
        return (
          <li key={product.id} className="product">
            <div className="product-body">
              <h2>{product.name}</h2>
              <p className="muted">{product.description}</p>
            </div>
            <div className="product-foot">
              <div>
                <div className="price">{formatPrice(product.priceCents)}</div>
                <div className={soldOut ? 'stock stock-out' : 'stock'}>
                  {soldOut ? 'Sold out' : `${product.stock} in stock`}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onAdd(product)}
                disabled={soldOut || maxed}
                aria-label={`Add ${product.name} to cart`}
              >
                {inCart > 0 ? `In cart (${inCart})` : 'Add to cart'}
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
