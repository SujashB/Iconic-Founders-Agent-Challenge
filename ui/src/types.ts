export type NodeStatus = "idle" | "active" | "complete" | "skipped" | "error";

export interface StatusResponse {
  o365_connected: boolean;
  composio_configured: boolean;
  composio_connected: boolean;
  composio_tools: string[];
  llm_provider: string;
  llm_model: string;
  sentiment_llm_model: string;
  llm_configured: boolean;
  beam_configured: boolean;
  fixtures: string[];
}

export interface NodeEvent {
  node: string;
  ts: string;
  delta: Record<string, unknown>;
}

export interface PipelineDone {
  ts: string;
  final_draft: { subject: string; body: string; signature: string } | null;
  outlook_draft_id: string | null;
  error: string | null;
}

export interface PipelineState {
  nodeStatuses: Record<string, NodeStatus>;
  nodeDeltas: Record<string, Record<string, unknown>>;
  finalDraft: PipelineDone["final_draft"];
  outlookDraftId: string | null;
  error: string | null;
  isRunning: boolean;
  log: string[];
  approved: boolean;
}
