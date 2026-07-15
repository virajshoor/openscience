export type Role = "user" | "assistant" | "tool";

export interface ChatMessage {
  id: string;
  role: Role;
  content: string;
  toolCalls?: ToolCall[];
  toolResult?: unknown;
  viewer?: ViewerArtifact;
  ts: number;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export type ViewerArtifact =
  | { type: "protein"; src: string; label: string }
  | { type: "genome"; src: string; label: string }
  | { type: "chem"; smiles: string; label: string }
  | { type: "figure"; src: string; label: string; format: "png" | "svg" | "html" | "jpg" | "pdf" };

export interface LLMConfig {
  baseUrl: string;
  apiKey: string;
  model: string;
  temperature: number;
  useTools: boolean;
}

export interface RunSummary {
  run_id: string;
  started_at: number;
  model?: string;
  review?: "pass" | "flag" | "fail" | "error" | null;
}

export interface RunDetail {
  manifest: Record<string, unknown>;
  conversation: Array<Record<string, unknown>>;
  review?: Record<string, unknown>;
  outputs?: string[];
  provenance?: Record<string, unknown>;
}

export interface ComputeBackendInfo {
  name: string;
  type: string;
}