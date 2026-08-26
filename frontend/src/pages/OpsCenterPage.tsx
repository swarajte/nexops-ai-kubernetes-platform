import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listAnalyses, listIncidents, requestAnalysis } from "../api/platform";
import type { Analysis, Decision, Incident } from "../types/platform";

const SERVICES = ["frontend", "orders-api", "payment-api"];
const POLL_MS = 10_000;
const ANALYSIS_GRACE_MS = 25_000;

function shortTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function actionLabel(analysis?: Analysis) {
  return analysis?.suggested_action?.type?.replace(/_/g, " ") ?? "Analyzing";
}

export default function OpsCenterPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [selectedId, setSelectedId] = useState<string>();
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [lastUpdated, setLastUpdated] = useState<Date>();
  const requested = useRef(new Set<string>());

  const refresh = useCallback(async () => {
    try {
      const [nextIncidents, nextAnalyses] = await Promise.all([
        listIncidents(),
        listAnalyses(),
      ]);
      setIncidents(nextIncidents);
      setAnalyses(nextAnalyses);
      setSelectedId((current) => {
        if (current && nextIncidents.some((incident) => incident.id === current)) {
          return current;
        }
        return nextIncidents.find((incident) => incident.status === "OPEN")?.id
          ?? nextIncidents[0]?.id;
      });
      setLastUpdated(new Date());
      setError(undefined);

      const analyzedIds = new Set(nextAnalyses.map((analysis) => analysis.incident_id));
      const now = Date.now();
      for (const incident of nextIncidents) {
        const age = now - new Date(incident.created_at).valueOf();
        if (
          incident.status === "OPEN"
          && !analyzedIds.has(incident.id)
          && age >= ANALYSIS_GRACE_MS
          && !requested.current.has(incident.id)
        ) {
          requested.current.add(incident.id);
          void requestAnalysis(incident.id)
            .then((analysis) => setAnalyses((current) => [analysis, ...current]))
            .catch(() => requested.current.delete(incident.id));
        }
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Control-plane API unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), POLL_MS);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const openIncidents = useMemo(
    () => incidents.filter((incident) => incident.status === "OPEN"),
    [incidents],
  );
  const resolvedIncidents = useMemo(
    () => incidents.filter((incident) => incident.status === "RESOLVED"),
    [incidents],
  );
  const selected = incidents.find((incident) => incident.id === selectedId);
  const selectedAnalysis = selected
    ? analyses.find(
        (analysis) =>
          analysis.incident_id === selected.id
          && analysis.incident_problem === selected.problem,
      ) ?? analyses.find((analysis) => analysis.incident_id === selected.id)
    : undefined;
  const decision = selected ? decisions[selected.id] : undefined;

  function decide(value: Decision) {
    if (!selected || selected.status !== "OPEN") return;
    setDecisions((current) => ({ ...current, [selected.id]: value }));
  }

  return (
    <main className="ops-shell">
      <header className="ops-header">
        <div>
          <a className="ops-wordmark" href="/ops">NEXOPS</a>
          <span className="ops-product">Control Center</span>
        </div>
        <div className="ops-header-actions">
          <span className={`live-state ${error ? "degraded" : ""}`}>
            <span className="live-dot" />
            {error ? "API degraded" : "Live"}
          </span>
          <button className="refresh-button" type="button" onClick={() => void refresh()}>
            Refresh
          </button>
          <a className="store-link" href="/store">Store</a>
        </div>
      </header>

      <div className="ops-content">
        <section className="ops-intro">
          <div>
            <p className="eyebrow">Kubernetes · nexops namespace</p>
            <h1>Operations overview</h1>
            <p>
              Incidents are correlated with rule-based AI analysis and evidence.
              Remediation remains human-controlled.
            </p>
          </div>
          <div className="updated-at" aria-live="polite">
            {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Connecting…"}
          </div>
        </section>

        {error && (
          <div className="ops-alert" role="alert">
            <strong>Unable to refresh platform data.</strong>
            <span>{error}. Existing results remain visible; retrying every 10 seconds.</span>
          </div>
        )}

        <section className="health-grid" aria-label="Application health">
          {SERVICES.map((service) => {
            const active = openIncidents.filter((incident) => incident.service === service);
            return (
              <article className={`health-card ${active.length ? "unhealthy" : "healthy"}`} key={service}>
                <div className="health-card-top">
                  <span className="service-icon">{service.slice(0, 2).toUpperCase()}</span>
                  <span className={`health-badge ${active.length ? "bad" : "good"}`}>
                    {active.length ? "Incident" : "Healthy"}
                  </span>
                </div>
                <h2>{service}</h2>
                <p>
                  {active.length
                    ? active.map((incident) => incident.problem).join(", ")
                    : "No open incidents"}
                </p>
              </article>
            );
          })}
        </section>

        <section className="ops-metrics" aria-label="Incident summary">
          <div><strong>{openIncidents.length}</strong><span>Open incidents</span></div>
          <div><strong>{resolvedIncidents.length}</strong><span>Resolved</span></div>
          <div><strong>{analyses.length}</strong><span>Analyses stored</span></div>
          <div><strong>10s</strong><span>Refresh interval</span></div>
        </section>

        <section className="incident-workspace">
          <div className="incident-list-panel">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Detector feed</p>
                <h2>Incidents</h2>
              </div>
              <span className="count-badge">{incidents.length}</span>
            </div>

            {loading && <div className="empty-state">Loading detector feed…</div>}
            {!loading && incidents.length === 0 && (
              <div className="empty-state">
                <strong>All systems clear</strong>
                <span>No incidents have been recorded.</span>
              </div>
            )}

            <div className="incident-list">
              {incidents.map((incident) => {
                const analysis = analyses.find(
                  (item) => item.incident_id === incident.id
                    && item.incident_problem === incident.problem,
                );
                return (
                  <button
                    className={`incident-row ${incident.id === selectedId ? "selected" : ""}`}
                    key={incident.id}
                    type="button"
                    onClick={() => setSelectedId(incident.id)}
                  >
                    <span className={`severity-marker ${incident.status.toLowerCase()}`} />
                    <span className="incident-row-main">
                      <span>
                        <strong>{incident.problem}</strong>
                        <span className={`incident-status ${incident.status.toLowerCase()}`}>
                          {incident.status}
                        </span>
                      </span>
                      <small>{incident.service} · {incident.pod}</small>
                    </span>
                    <span className="incident-row-meta">
                      <small>{shortTime(incident.updated_at)}</small>
                      <span>{actionLabel(analysis)} →</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="incident-detail-panel">
            {!selected && (
              <div className="empty-state detail-empty">
                <strong>Select an incident</strong>
                <span>Evidence and analysis will appear here.</span>
              </div>
            )}

            {selected && (
              <>
                <div className="detail-heading">
                  <div>
                    <span className={`incident-status ${selected.status.toLowerCase()}`}>
                      {selected.status}
                    </span>
                    <h2>{selected.problem}</h2>
                    <p>{selected.service} · {selected.namespace} · {selected.pod}</p>
                  </div>
                  <span className="incident-id">ID {selected.id.slice(0, 8)}</span>
                </div>

                <div className="detail-message">{selected.message}</div>

                <div className="detail-columns">
                  <section>
                    <h3>Detector evidence</h3>
                    <pre>{JSON.stringify(selected.evidence, null, 2)}</pre>
                    <dl className="incident-facts">
                      <div><dt>Created</dt><dd>{shortTime(selected.created_at)}</dd></div>
                      <div><dt>Updated</dt><dd>{shortTime(selected.updated_at)}</dd></div>
                      <div><dt>Fingerprint</dt><dd>{selected.fingerprint}</dd></div>
                    </dl>
                  </section>

                  <section className="analysis-section">
                    <div className="analysis-title">
                      <h3>AI analysis</h3>
                      {selectedAnalysis && (
                        <span>{selectedAnalysis.source} · {selectedAnalysis.confidence}%</span>
                      )}
                    </div>
                    {!selectedAnalysis && (
                      <div className="analyzing-state">
                        <span className="analyzing-pulse" />
                        <div>
                          <strong>Analysis in progress</strong>
                          <p>The analyzer polls OPEN incidents every 20 seconds.</p>
                        </div>
                      </div>
                    )}
                    {selectedAnalysis && (
                      <>
                        <div className="analysis-block">
                          <span>Problem</span>
                          <p>{selectedAnalysis.problem}</p>
                        </div>
                        <div className="analysis-block">
                          <span>Likely cause</span>
                          <p>{selectedAnalysis.likely_cause}</p>
                        </div>
                        <div className="analysis-block">
                          <span>Evidence</span>
                          <ul>
                            {selectedAnalysis.evidence.map((item, index) => (
                              <li key={`${item}-${index}`}>{item}</li>
                            ))}
                          </ul>
                        </div>
                        <div className="recommendation">
                          <span>Recommended fix</span>
                          <strong>{selectedAnalysis.suggested_fix}</strong>
                          <code>{selectedAnalysis.suggested_action.type}</code>
                        </div>
                      </>
                    )}
                  </section>
                </div>

                <section className="approval-bar">
                  <div>
                    <span>Human decision</span>
                    <strong>
                      {selected.status === "RESOLVED"
                        ? "Recovery verified"
                        : decision === "approved"
                          ? "Approved — awaiting Stage 9 remediation service"
                          : decision === "rejected"
                            ? "Recommendation rejected"
                            : "Review the recommendation before deciding"}
                    </strong>
                  </div>
                  <div className="approval-actions">
                    <button
                      className="reject-button"
                      type="button"
                      disabled={!selectedAnalysis || selected.status === "RESOLVED"}
                      onClick={() => decide("rejected")}
                    >
                      Reject
                    </button>
                    <button
                      className="approve-button"
                      type="button"
                      disabled={!selectedAnalysis || selected.status === "RESOLVED"}
                      onClick={() => decide("approved")}
                    >
                      Approve recommendation
                    </button>
                  </div>
                </section>

                <div className="remediation-track">
                  <span className="complete">Detected</span>
                  <span className={selectedAnalysis ? "complete" : "current"}>Analyzed</span>
                  <span className={decision ? "complete" : "pending"}>Decision</span>
                  <span className="pending">Remediation · Stage 9</span>
                  <span className={selected.status === "RESOLVED" ? "complete" : "pending"}>
                    Recovery
                  </span>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
