import { useEffect, useState } from "react";
import { checkOrdersHealth, placeOrder, type OrderResponse } from "../api/orders";
import { PRODUCTS, type Product } from "../data/products";

type OrderState =
  | { kind: "idle" }
  | { kind: "loading"; productName: string }
  | { kind: "success"; order: OrderResponse }
  | { kind: "error"; message: string };

export default function StorePage() {
  const [apiHealthy, setApiHealthy] = useState<boolean | null>(null);
  const [orderState, setOrderState] = useState<OrderState>({ kind: "idle" });

  useEffect(() => {
    let active = true;
    checkOrdersHealth().then((healthy) => {
      if (active) setApiHealthy(healthy);
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleBuy(product: Product) {
    setOrderState({ kind: "loading", productName: product.name });
    try {
      const order = await placeOrder({
        product_id: product.id,
        product_name: product.name,
        quantity: 1,
        unit_price: product.price,
      });
      setOrderState({ kind: "success", order });
      setApiHealthy(true);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unable to place order";
      setOrderState({ kind: "error", message });
      setApiHealthy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">NexOps Store</div>
          <div className="brand-sub">The application under watch</div>
        </div>
        <div className="store-actions">
          <div className="status-pill" aria-live="polite">
            <span
              className={`status-dot ${apiHealthy === true ? "ok" : apiHealthy === false ? "bad" : ""}`}
            />
            {apiHealthy === null && "Checking orders-api"}
            {apiHealthy === true && "orders-api healthy"}
            {apiHealthy === false && "orders-api unreachable"}
          </div>
          <a className="ops-link" href="/ops">Open Control Center</a>
        </div>
      </header>

      <section className="hero">
        <h1>Reliable gear for recovery nights.</h1>
        <p>
          Browse the catalog, place an order, and watch payment flow through
          orders-api into payment-api.
        </p>
      </section>

      <section className="catalog" aria-label="Product catalog">
        {PRODUCTS.map((product) => (
          <article className="product" key={product.id}>
            <div className="product-tag">{product.tag}</div>
            <h2>{product.name}</h2>
            <p>{product.description}</p>
            <div className="product-footer">
              <div className="price">${product.price.toFixed(2)}</div>
              <button
                className="buy-button"
                type="button"
                disabled={orderState.kind === "loading"}
                onClick={() => handleBuy(product)}
              >
                {orderState.kind === "loading" && orderState.productName === product.name
                  ? "Placing..."
                  : "Buy now"}
              </button>
            </div>
          </article>
        ))}
      </section>

      {orderState.kind === "success" && (
        <section className="result-panel success" aria-live="polite">
          <h3>Order confirmed</h3>
          <p>{orderState.order.message}</p>
          <p>
            Order ID: {orderState.order.order_id} | Payment: {orderState.order.payment_id}
          </p>
          <p>
            Total: ${orderState.order.total_amount.toFixed(2)} {orderState.order.currency}
          </p>
        </section>
      )}

      {orderState.kind === "error" && (
        <section className="result-panel error" aria-live="polite">
          <h3>Order failed</h3>
          <p>{orderState.message}</p>
        </section>
      )}
    </div>
  );
}
