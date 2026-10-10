import type { Order, Product } from './types';

// Relative URLs on purpose: the gateway in front of this app (Kubernetes
// Gateway, docker-compose gateway, or the Vite dev proxy) routes /api/<service>
// to the right backend. The same build runs unchanged in every environment.
const CATALOG = '/api/catalog/v1';
const ORDERS = '/api/orders/v1';

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: { 'content-type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError(0, 'Network error. Check your connection and try again.');
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    // Fastify errors use "message", FastAPI errors use "detail".
    const detail = body.message ?? (typeof body.detail === 'string' ? body.detail : undefined);
    throw new ApiError(response.status, detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function listProducts(): Promise<Product[]> {
  const body = await request<{ items: Product[] }>(`${CATALOG}/products?limit=100`);
  return body.items;
}

export function placeOrder(
  customerEmail: string,
  items: { productId: string; quantity: number }[],
): Promise<Order> {
  return request<Order>(`${ORDERS}/orders`, {
    method: 'POST',
    body: JSON.stringify({ customerEmail, items }),
  });
}

export function orderErrorMessage(err: unknown): string {
  if (!(err instanceof ApiError)) return 'Something went wrong. Please try again.';
  switch (err.status) {
    case 409:
      return 'Sorry, one of the items no longer has enough stock. Stock has been refreshed.';
    case 422:
      return 'Please check your email address and cart, then try again.';
    case 503:
      return 'Ordering is temporarily unavailable. Please try again in a moment.';
    default:
      return err.message;
  }
}
