import type { Analysis, Incident } from "../types/platform";

async function readJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`.trim());
  }
  return response.json() as Promise<T>;
}

export async function listIncidents(): Promise<Incident[]> {
  const body = await readJson<{ incidents: Incident[] }>(
    "/ops-api/detector/incidents",
  );
  return body.incidents;
}

export async function listAnalyses(): Promise<Analysis[]> {
  const body = await readJson<{ analyses: Analysis[] }>(
    "/ops-api/analyzer/analyses",
  );
  return body.analyses;
}

export function requestAnalysis(incidentId: string): Promise<Analysis> {
  return readJson<Analysis>("/ops-api/analyzer/analyze", {
    method: "POST",
    body: JSON.stringify({ incident_id: incidentId }),
  });
}
