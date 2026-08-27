import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const incident = {
  id: "incident-current",
  service: "payment-api",
  problem: "HighErrorRate",
  status: "OPEN",
  pod: "payment-api-broken",
  namespace: "nexops",
  message: "payment-api FAILURE_MODE=errors (/pay returns 500s)",
  evidence: { source: "fail_status", problem: "HighErrorRate" },
  fingerprint: "payment-api:HighErrorRate",
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

const analysis = {
  id: "analysis-current",
  incident_id: incident.id,
  service: "payment-api",
  incident_problem: "HighErrorRate",
  incident_status: "OPEN",
  problem: "payment-api is injecting HTTP errors.",
  evidence: ["error_rate=0.8", "pod remains Ready"],
  likely_cause: "Intentional errors failure mode is enabled.",
  suggested_fix: "Reset the payment-api failure mode.",
  suggested_action: { type: "reset_failure_mode", target: "payment-api" },
  confidence: 85,
  source: "rules",
  created_at: new Date().toISOString(),
};

const remediation = {
  id: "remediation-current",
  incident_id: incident.id,
  analysis_id: analysis.id,
  decision: "approved",
  status: "queued",
  suggested_action: analysis.suggested_action,
  applied: null,
  steps: [],
  message: "Decision recorded",
  error: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.restoreAllMocks();
});

describe("NexOps Control Center", () => {
  it("joins analysis by incident id and shows Ready-but-failing incidents", async () => {
    window.history.replaceState({}, "", "/ops");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        let body: unknown;
        if (url.includes("/incidents")) {
          body = { incidents: [incident] };
        } else if (url.includes("/remediation/decisions") && init?.method === "POST") {
          body = remediation;
        } else if (url.includes("/remediation/remediations")) {
          body = { remediations: [] };
        } else {
          body = {
            analyses: [
              { ...analysis, id: "wrong", incident_id: "old-incident", confidence: 12 },
              analysis,
            ],
          };
        }
        return Promise.resolve({
          ok: true,
          json: async () => body,
        });
      }),
    );

    render(<App />);

    expect((await screen.findAllByText("HighErrorRate")).length).toBeGreaterThan(0);
    expect(screen.getByText("payment-api is injecting HTTP errors.")).toBeInTheDocument();
    expect(screen.getByText("rules · 85%")).toBeInTheDocument();
    expect(screen.getByText("pod remains Ready")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Approve recommendation" }));
    expect(
      await screen.findByText("Approved — queued for remediation"),
    ).toBeInTheDocument();
    const calls = vi.mocked(fetch).mock.calls;
    const post = calls.find(([url]) => String(url).includes("/remediation/decisions"));
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      incident_id: incident.id,
      analysis_id: analysis.id,
      decision: "approved",
    });
  });

  it("shows healthy services when there are no open incidents", async () => {
    window.history.replaceState({}, "", "/ops");
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => Promise.resolve({
        ok: true,
        json: async () => String(input).includes("/incidents")
          ? { incidents: [] }
          : String(input).includes("/remediation/remediations")
            ? { remediations: [] }
            : { analyses: [] },
      })),
    );

    render(<App />);

    expect(await screen.findByText("All systems clear")).toBeInTheDocument();
    expect(screen.getAllByText("No open incidents")).toHaveLength(3);
  });
});
