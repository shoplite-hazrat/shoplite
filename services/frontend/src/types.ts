// Mirrors the JSON returned by catalog-service and order-service.

export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string;
  priceCents: number;
  stock: number;
}

export interface OrderItem {
  productId: string;
  productName: string;
  unitPriceCents: number;
  quantity: number;
}

export interface Order {
  id: string;
  customerEmail: string;
  status: string;
  totalCents: number;
  createdAt: string;
  items: OrderItem[];
}
