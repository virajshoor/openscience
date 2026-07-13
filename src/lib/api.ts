import { getSidecarUrl, useSession } from "../stores/session";
import type { ChatMessage, LLMConfig, RunDetail, RunSummary } from "./types";

const u = () => getSidecarUrl();

function sidecarConfig(config: LLMConfig) {
  return {
    base_url: config.baseUrl,
    api_key: config.apiKey,
    model: config.model,
    temperature: config.temperature,
    use_tools: config.useTools,
  };
}

export async function checkHealth(): Promise<boolean> {
  try {
    const r = await fetch(`${u()}/health`, { method: "GET" });
    if (!r.ok) return false;
    const data = await r.json();
    return !!data.ok;
  } catch {
    return false;
  }
}

export async function fetchTools() {
  const r = await fetch(`${u()}/tools`);
  if (!r.ok) return { tools: [] };
  return r.json();
}

export async function fetchRuns(): Promise<RunSummary[]> {
  try {
    const r = await fetch(`${u()}/runs`);
    if (!r.ok) return [];
    const data = await r.json();
    return data.runs ?? [];
  } catch {
    return [];
  }
}

export async function fetchRun(runId: string): Promise<RunDetail> {
  const r = await fetch(`${u()}/runs/${runId}`);
  if (!r.ok) throw new Error(`Run ${runId}: HTTP ${r.status}`);
  return r.json();
}

export async function reviewRun(runId: string) {
  const cfg = useSession.getState().config;
  const r = await fetch(`${u()}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, config: sidecarConfig(cfg) }),
  });
  if (!r.ok) return { error: `HTTP ${r.status}` };
  return r.json();
}

export async function exportRun(runId: string): Promise<void> {
  const r = await fetch(`${u()}/runs/${runId}`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const data = await r.json();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `openscience-run-${runId}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function verifyRun(runId: string): Promise<{ ok: boolean; outputs: Array<{ name: string; valid: boolean }> }> {
  const r = await fetch(`${u()}/runs/${runId}/verify`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

interface StreamCallbacks {
  onToken: (t: string) => void;
  onToolCall: (call: { id: string; name: string; arguments: Record<string, unknown> }) => void;
  onToolResult: (id: string, name: string, result: unknown) => void;
  onViewer: (v: ChatMessage["viewer"]) => void;
  onDone: (runId: string) => void;
  onError: (msg: string) => void;
}

export async function streamChat(
  messages: Array<{ role: string; content: string }>,
  cb: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const { config, computeBackend } = useSession.getState();
  let r: Response;
  try {
    r = await fetch(`${u()}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        config: sidecarConfig(config),
        compute: computeBackend,
      }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return;
    cb.onError(`Cannot reach sidecar: ${String(e)}`);
    return;
  }

  if (!r.ok || !r.body) {
    cb.onError(`Sidecar returned ${r.status}`);
    return;
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    let result: ReadableStreamReadResult<Uint8Array>;
    try {
      result = await reader.read();
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      cb.onError(`Stream read error: ${String(e)}`);
      return;
    }
    const { value, done } = result;
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const trimmed = part.replace(/\r$/, "").trim();
      if (!trimmed.startsWith("data:")) continue;
      const payload = trimmed.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const evt = JSON.parse(payload);
        const t = evt.event;
        const d = evt.data;
        if (t === "token") cb.onToken(typeof d === "string" ? d : d.text);
        else if (t === "tool_call") cb.onToolCall(d);
        else if (t === "tool_result") cb.onToolResult(d.id, d.name, d.result);
        else if (t === "viewer") cb.onViewer(d);
        else if (t === "done") cb.onDone(d.run_id);
        else if (t === "error") cb.onError(d.message || "error");
      } catch {
        // ignore unparseable
      }
    }
  }
}

export async function configureSSH(host: string, user: string, port: number, keyPath?: string) {
  const r = await fetch(`${u()}/compute/ssh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ host, user, port, key_path: keyPath }),
  });
  return r.ok;
}

export async function listCompute() {
  try {
    const r = await fetch(`${u()}/compute`);
    if (!r.ok) return { backends: [{ name: "local", type: "local" }] };
    return r.json();
  } catch {
    return { backends: [{ name: "local", type: "local" }] };
  }
}

export async function loadPersistedConfig(): Promise<Record<string, unknown> | null> {
  try {
    const r = await fetch(`${u()}/config`);
    if (!r.ok) return null;
    const data = await r.json();
    if (data && Object.keys(data).length > 0) return data;
    return null;
  } catch {
    return null;
  }
}

export async function persistConfig(cfg: Record<string, unknown>): Promise<void> {
  try {
    await fetch(`${u()}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
  } catch {
    // best-effort
  }
}
