export type OrderRequest = {
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
};

export type OrderResponse = {
  order_id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_amount: number;
  currency: string;
  status: string;
  payment_status: string;
  payment_id?: string;
  message: string;
};

const ORDERS_API_BASE = (import.meta.env.VITE_ORDERS_API_URL as string | undefined)?.replace(/\/$/, "") || "/api";

export async function placeOrder(payload: OrderRequest): Promise<OrderResponse> {
  const response = await fetch(`${ORDERS_API_BASE}/orders`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = `Order failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // keep default message
    }
    throw new Error(detail);
  }

  return response.json();
}

export async function checkOrdersHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${ORDERS_API_BASE}/health`);
    if (!response.ok) {
      return false;
    }
    const body = await response.json();
    return body.status === "healthy";
  } catch {
    return false;
  }
}
