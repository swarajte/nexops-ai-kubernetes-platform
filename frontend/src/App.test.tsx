import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import App from "./App";

describe("NexOps Store", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the store brand and products", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "healthy", service: "orders-api" }),
      }),
    );

    render(<App />);

    expect(screen.getByText("NexOps Store")).toBeInTheDocument();
    expect(screen.getByText("Signal Monitor")).toBeInTheDocument();
    expect(screen.getByText("On-Call Mug")).toBeInTheDocument();
    expect(await screen.findByText("orders-api healthy")).toBeInTheDocument();
  });
});
