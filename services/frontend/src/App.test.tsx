import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { Product } from './types';

const products: Product[] = [
  { id: 'p1', sku: 'MUG', name: 'Kubernetes Mug', description: 'A mug', priceCents: 1299, stock: 3 },
  { id: 'p2', sku: 'CAP', name: 'Helm Cap', description: 'A cap', priceCents: 2499, stock: 0 },
];

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

type Handler = (url: string, init?: RequestInit) => Promise<Response>;

function stubFetch(handler: Handler) {
  const fetchMock = vi.fn(handler);
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('App', () => {
  let orderResponse: () => Promise<Response>;
  let fetchMock: ReturnType<typeof stubFetch>;

  beforeEach(() => {
    orderResponse = () =>
      json(201, {
        id: 'order-1',
        customerEmail: 'ada@example.com',
        status: 'confirmed',
        totalCents: 2598,
        createdAt: '2026-10-10T00:00:00Z',
        items: [{ productId: 'p1', productName: 'Kubernetes Mug', unitPriceCents: 1299, quantity: 2 }],
      });
    fetchMock = stubFetch((url) => {
      if (url.startsWith('/api/catalog/v1/products')) return json(200, { items: products });
      if (url === '/api/orders/v1/orders') return orderResponse();
      return json(404, {});
    });
  });

  it('lists products through the gateway path and marks sold-out items', async () => {
    render(<App />);
    expect(await screen.findByText('Kubernetes Mug')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/catalog/v1/products?limit=100', expect.anything());
    expect(screen.getByText('Sold out')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add Helm Cap to cart' })).toBeDisabled();
  });

  it('places an order and shows the confirmation', async () => {
    const user = userEvent.setup();
    render(<App />);

    const add = await screen.findByRole('button', { name: 'Add Kubernetes Mug to cart' });
    await user.click(add);
    await user.click(add);
    expect(screen.getByTestId('cart-total')).toHaveTextContent('$25.98');

    await user.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await user.click(screen.getByRole('button', { name: 'Place order' }));

    const confirmation = await screen.findByRole('region', { name: /order is confirmed/i });
    expect(within(confirmation).getByText('ada@example.com')).toBeInTheDocument();
    expect(within(confirmation).getByTestId('order-total')).toHaveTextContent('$25.98');

    const orderCall = fetchMock.mock.calls.find(([url]) => url === '/api/orders/v1/orders');
    expect(JSON.parse(orderCall?.[1]?.body as string)).toEqual({
      customerEmail: 'ada@example.com',
      items: [{ productId: 'p1', quantity: 2 }],
    });

    await user.click(screen.getByRole('button', { name: 'Continue shopping' }));
    expect(screen.getByText('Your cart is empty.')).toBeInTheDocument();
  });

  it('explains an out-of-stock failure and keeps the cart', async () => {
    orderResponse = () => json(409, { detail: 'insufficient stock for product p1' });
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Add Kubernetes Mug to cart' }));
    await user.type(screen.getByLabelText(/email/i), 'ada@example.com');
    await user.click(screen.getByRole('button', { name: 'Place order' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/no longer has enough stock/);
    expect(screen.getByLabelText('Kubernetes Mug quantity')).toHaveTextContent('1');
  });

  it('shows a retryable error when the catalog is down', async () => {
    let up = false;
    stubFetch(() => (up ? json(200, { items: products }) : json(503, { message: 'unavailable' })));
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent('unavailable');
    up = true;
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Kubernetes Mug')).toBeInTheDocument();
  });
});
