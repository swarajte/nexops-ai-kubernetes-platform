export type IncidentStatus = "OPEN" | "RESOLVED";

export type Incident = {
  id: string;
  service: string;
  problem: string;
  status: IncidentStatus;
  pod: string;
  namespace: string;
  message: string;
  evidence: Record<string, unknown>;
  fingerprint: string;
  created_at: string;
  updated_at: string;
};

export type SuggestedAction = {
  type: string;
  target?: string;
  from?: string;
  to?: string;
  [key: string]: unknown;
};

export type Analysis = {
  id: string;
  incident_id: string;
  service: string;
  incident_problem: string;
  incident_status: IncidentStatus;
  problem: string;
  evidence: string[];
  likely_cause: string;
  suggested_fix: string;
  suggested_action: SuggestedAction;
  confidence: number;
  source: "rules" | "llm" | string;
  created_at: string;
};

export type Decision = "approved" | "rejected";
