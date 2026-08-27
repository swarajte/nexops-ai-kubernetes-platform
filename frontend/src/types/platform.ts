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

export type RemediationStatus =
  | "rejected"
  | "queued"
  | "validating"
  | "applying"
  | "verifying"
  | "succeeded"
  | "failed";

export type Remediation = {
  id: string;
  incident_id: string;
  analysis_id: string;
  decision: Decision;
  status: RemediationStatus;
  suggested_action: SuggestedAction;
  applied?: Record<string, unknown> | null;
  steps: Array<{ at: string; step: string; detail: string }>;
  message: string;
  error?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type SubmitDecisionBody = {
  incident_id: string;
  analysis_id: string;
  decision: Decision;
};
