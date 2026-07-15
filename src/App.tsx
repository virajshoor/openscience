import { useEffect, useRef, useState } from "react";
import { IconSettings, IconRefresh, IconBrain, IconMicroscope, IconHistory } from "@tabler/icons-react";
import openScienceLogo from "./assets/openscience-logo.svg";
import { getSidecarUrl, useSession, setSidecarUrl } from "./stores/session";
import { checkHealth, fetchRuns, fetchRun, streamChat, loadPersistedConfig, persistConfig, listAgents, listSkills } from "./lib/api";
import ChatPanel from "./components/ChatPanel";
import ViewerPanel from "./components/ViewerPanel";
import RunInspector from "./components/RunInspector";
import RunHistory from "./components/RunHistory";
import SettingsModal from "./components/SettingsModal";
import ManuscriptPanel from "./components/ManuscriptPanel";
import type { ChatMessage } from "./lib/types";

async function discoverSidecarPort(): Promise<number | null> {
  try {
    const w = window as unknown as { __TAURI__?: { core?: { invoke?: (cmd: string) => Promise<unknown> } } };
    const invoke = w.__TAURI__?.core?.invoke;
    if (!invoke) return null;
    const port = (await invoke("sidecar_port")) as number;
    return port || null;
  } catch {
    return null;
  }
}

/** Probe a localhost port for a healthy sidecar. */
async function probePort(port: number): Promise<boolean> {
  try {
    const r = await fetch(`http://127.0.0.1:${port}/health`, { method: "GET" });
    if (!r.ok) return false;
    const d = await r.json();
    return !!d?.ok;
  } catch {
    return false;
  }
}

/**
 * Robustly locate the sidecar. The Tauri shell's `sidecar_port` IPC is
 * authoritative (it's the port THIS app picked), but it may not be ready on
 * the first mount. If IPC fails or returns 0, scan the candidate port range
 * for a healthy sidecar. This self-heals when port 7100 is held by a stale
 * process and the shell had to pick a different port.
 */
async function findSidecarPort(currentPort: number): Promise<number | null> {
  const ipcPort = await discoverSidecarPort();
  if (ipcPort && ipcPort !== currentPort && await probePort(ipcPort)) {
    return ipcPort;
  }
  if (ipcPort && ipcPort === currentPort) {
    return currentPort; // already pointing at the authoritative port
  }
  // Scan fallback (covers browser-without-Tauri and IPC-race cases).
  const candidates = [7100, 7101, 7102, 7103, 7104, 7105, 7106, 7107, 7108, 7109, 7110];
  for (const p of candidates) {
    if (p === currentPort) continue;
    if (await probePort(p)) return p;
  }
  return null;
}

function conversationToMessages(run: { conversation?: Array<Record<string, unknown>> }): ChatMessage[] {
  const out: ChatMessage[] = [];
  for (const entry of run.conversation ?? []) {
    const role = entry["role"] as ChatMessage["role"];
    const payload = entry["payload"] as Record<string, unknown> | undefined;
    if (!payload) continue;
    if (role === "assistant") {
      const content = (payload["content"] as string) || "";
      const toolCalls = (payload["tool_calls"] as Array<{ id: string; function: { name: string; arguments: string } }>) || [];
      if (content || toolCalls.length) {
        out.push({
          id: crypto.randomUUID(),
          role: "assistant",
          content,
          ts: Date.now(),
          ...(toolCalls.length
            ? {
                toolCalls: toolCalls.map((tc) => ({
                  id: tc.id,
                  name: tc.function.name,
                  arguments: JSON.parse(tc.function.arguments || "{}"),
                })),
              }
            : {}),
        });
      }
    } else if (role === "user") {
      const content = (payload["content"] as string) || "";
      if (content) out.push({ id: crypto.randomUUID(), role: "user", content, ts: Date.now() });
    } else if (role === "tool") {
      const tool = payload["tool"] as string;
      const result = payload["result"] as Record<string, unknown>;
      const summary = result?.["summary"] as string;
      out.push({ id: crypto.randomUUID(), role: "tool", content: `${tool}: ${summary || ""}`, ts: Date.now() });
    }
  }
  return out;
}

const COMPOUNDING_SYSTEM_PROMPT = `You are OpenScience, an AI research assistant specialized in scientific data.
Below is an accumulated understanding of the user's research context, built from prior conversations.
Use this to provide more accurate, contextual responses. Do not mention this context explicitly.

Accumulated science context:
{science_context}`;

export default function App() {
  const setSidecarOnline = useSession((s) => s.setSidecarOnline);
  const sidecarOnline = useSession((s) => s.sidecarOnline);
  const sidecarStarting = useSession((s) => s.sidecarStarting);
  const setSidecarStarting = useSession((s) => s.setSidecarStarting);
  const setRuns = useSession((s) => s.setRuns);
  const runs = useSession((s) => s.runs);
  const clear = useSession((s) => s.clear);
  const messages = useSession((s) => s.messages);
  const streaming = useSession((s) => s.streaming);
  const setStreaming = useSession((s) => s.setStreaming);
  const setError = useSession((s) => s.setError);
  const error = useSession((s) => s.error);
  const setViewer = useSession((s) => s.setViewer);
  const viewer = useSession((s) => s.viewer);
  const pushMessage = useSession((s) => s.pushMessage);
  const appendAssistant = useSession((s) => s.appendAssistant);
  const chatCount = useSession((s) => s.chatCount);
  const incrementChatCount = useSession((s) => s.incrementChatCount);
  const scienceContext = useSession((s) => s.scienceContext);
  const setScienceContext = useSession((s) => s.setScienceContext);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [compounding, setCompounding] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const viewingRun = useRef(false);
  const rightPane = useSession((s) => s.rightPane);
  const setRightPane = useSession((s) => s.setRightPane);

  async function refresh() {
    // Re-locate the sidecar in case the port changed, then check health.
    const cur = getSidecarUrl();
    const curPort = parseInt(cur.split(":").pop() || "7100", 10);
    const found = await findSidecarPort(curPort);
    if (found && found !== curPort) {
      setSidecarUrl(`http://127.0.0.1:${found}`);
    }
    const ok = await checkHealth();
    setSidecarOnline(ok);
    if (ok) {
      const rs = await fetchRuns();
      setRuns(rs);
    }
  }

  useEffect(() => {
    let intervalId: ReturnType<typeof setInterval>;
    let online = false;

    async function poll() {
      // While offline, keep trying to (re)discover the sidecar port — the
      // Tauri IPC may not be ready on the first mount, and port 7100 may be
      // held by a stale process so the shell picked a different port.
      const cur = getSidecarUrl();
      const curPort = parseInt(cur.split(":").pop() || "7100", 10);
      const ipcPort = await discoverSidecarPort();
      let port = ipcPort;
      if (!port) port = await findSidecarPort(curPort);
      if (port && port !== curPort) {
        setSidecarUrl(`http://127.0.0.1:${port}`);
      }
      const ok = await checkHealth();
      setSidecarOnline(ok);
      // "starting" = the shell has spawned a sidecar (or one was found) but it
      // isn't healthy yet (cold PyInstaller extraction). Distinct from "offline".
      setSidecarStarting(!ok && (!!ipcPort || !!port));
      if (ok) {
        if (!online) {
          const rs = await fetchRuns();
          setRuns(rs);
        }
        online = true;
        clearInterval(intervalId);
        intervalId = setInterval(poll, 30000);
      } else {
        online = false;
        clearInterval(intervalId);
        intervalId = setInterval(poll, 2000);
      }
    }

    (async () => {
      const port = await discoverSidecarPort();
      if (port && port !== 7100) {
        setSidecarUrl(`http://127.0.0.1:${port}`);
      }
      const persisted = await loadPersistedConfig();
      if (persisted) {
        const c = persisted as Record<string, unknown>;
        if (c.base_url) useSession.getState().setConfig({ baseUrl: c.base_url as string });
        if (c.api_key) useSession.getState().setConfig({ apiKey: c.api_key as string });
        if (c.model) useSession.getState().setConfig({ model: c.model as string });
        if (c.temperature !== undefined) useSession.getState().setConfig({ temperature: c.temperature as number });
        if (c.use_tools !== undefined) useSession.getState().setConfig({ useTools: c.use_tools as boolean });
        if (c.compute) useSession.getState().setCompute(c.compute as string);
        if (c.require_approval !== undefined) useSession.getState().setRequireApproval(c.require_approval as boolean);
      }
      poll();
    })();
    return () => clearInterval(intervalId);
  }, []);

  useEffect(() => {
    function onLoadRun(e: Event) {
      const id = (e as CustomEvent<string>).detail;
      if (id) loadRunIntoChat(id);
    }
    window.addEventListener("openscience:load-run", onLoadRun as EventListener);
    return () => window.removeEventListener("openscience:load-run", onLoadRun as EventListener);
  }, []);

  const config = useSession((s) => s.config);
  const computeBackend = useSession((s) => s.computeBackend);
  const requireApproval = useSession((s) => s.requireApproval);
  const agent = useSession((s) => s.agent);
  const setAgent = useSession((s) => s.setAgent);
  const skill = useSession((s) => s.skill);
  const setSkill = useSession((s) => s.setSkill);
  const [agentList, setAgentList] = useState<{ name: string }[]>([]);
  const [skillList, setSkillList] = useState<{ name: string }[]>([]);
  useEffect(() => {
    if (!sidecarOnline) return;
    listAgents().then((a) => setAgentList(a));
    listSkills().then((s) => setSkillList(s));
  }, [sidecarOnline]);
  useEffect(() => {
    persistConfig({
      base_url: config.baseUrl,
      api_key: config.apiKey,
      model: config.model,
      temperature: config.temperature,
      use_tools: config.useTools,
      compute: computeBackend,
      require_approval: requireApproval,
    });
  }, [config, computeBackend, requireApproval]);

  async function loadRunIntoChat(runId: string) {
    viewingRun.current = true;
    setSelectedRunId(runId);
    clear();
    const run = await fetchRun(runId);
    const restored = conversationToMessages(run);
    for (const m of restored) pushMessage(m);
    // Restore the viewer from the run's tool results if present
    for (const entry of run.conversation ?? []) {
      const payload = entry["payload"] as Record<string, unknown> | undefined;
      if (payload?.["result"]) {
        const result = payload["result"] as Record<string, unknown>;
        const v = result["viewer"];
        if (v) setViewer(v as never);
      }
    }
  }

  function newConversation() {
    clear();
    setSelectedRunId(null);
    viewingRun.current = false;
  }

  async function maybeCompoundScienceContext() {
    const count = useSession.getState().chatCount;
    if (count > 0 && count % 10 === 0) {
      setCompounding(true);
      try {
        const recentMessages = useSession.getState().messages
          .filter((m) => (m.role === "user" || m.role === "assistant") && m.content)
          .slice(-40)
          .map((m) => `${m.role}: ${m.content}`)
          .join("\n\n");

        const existingContext = useSession.getState().scienceContext;
        const compoundPrompt = `You are building an accumulated understanding of a researcher's work.
Below is the existing context (if any) and recent conversation messages.
Synthesize a concise summary (max 500 words) of key scientific themes, tools used, entities studied,
methods, and patterns. This will help provide better responses in future conversations.

Existing context:
${existingContext || "(none yet)"}

Recent messages:
${recentMessages}

Output only the synthesized context, no preamble.`;

        const r = await fetch(`${getSidecarUrl()}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            messages: [{ role: "user", content: compoundPrompt }],
            config: {
              base_url: useSession.getState().config.baseUrl,
              api_key: useSession.getState().config.apiKey,
              model: useSession.getState().config.model,
              temperature: 0.1,
              use_tools: false,
            },
            compute: "local",
          }),
        });

        if (r.ok && r.body) {
          const reader = r.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";
          let contextText = "";
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const parts = buffer.split("\n\n");
            buffer = parts.pop() || "";
            for (const part of parts) {
              const trimmed = part.trim();
              if (!trimmed.startsWith("data:")) continue;
              const payload = trimmed.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;
              try {
                const evt = JSON.parse(payload);
                if (evt.event === "token" && evt.data?.text) contextText += evt.data.text;
              } catch { /* skip */ }
            }
          }
          if (contextText.trim()) {
            setScienceContext(contextText.trim());
          }
        }
      } catch {
        // best-effort, don't block the user
      } finally {
        setCompounding(false);
      }
    }
  }

  async function send(text: string) {
    if (!text.trim() || streaming) return;
    viewingRun.current = false;

    // Build history with science context as a system message if available
    const history: Array<{ role: string; content: string }> = [];
    const ctx = useSession.getState().scienceContext;
    if (ctx) {
      history.push({
        role: "system",
        content: COMPOUNDING_SYSTEM_PROMPT.replace("{science_context}", ctx),
      });
    }
    history.push(
      ...messages
        .filter((m) => (m.role === "user" || m.role === "assistant") && m.content)
        .map((m) => ({ role: m.role, content: m.content }))
    );
    history.push({ role: "user", content: text });

    const userMsg: ChatMessage = { id: crypto.randomUUID(), role: "user", content: text, ts: Date.now() };
    pushMessage(userMsg);
    const asstId = crypto.randomUUID();
    pushMessage({ id: asstId, role: "assistant", content: "", ts: Date.now() });
    setStreaming(true);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    let hasTokens = false;
    const timeoutId = setTimeout(() => {
      if (!hasTokens) {
        setError("No response from LLM within 30s. Check your endpoint and API key in Settings.");
        controller.abort();
        setStreaming(false);
      }
    }, 30000);

    try {
      await streamChat(history, {
        onToken: (t) => { hasTokens = true; appendAssistant(asstId, t); },
        onToolCall: (c) => {
          hasTokens = true;
          pushMessage({ id: crypto.randomUUID(), role: "tool", content: `${c.name}(${JSON.stringify(c.arguments)})`, toolCalls: [c], ts: Date.now() });
        },
        onToolResult: (id, name, result) => {
          const summary = typeof result === "object" && result && "summary" in (result as object) ? (result as Record<string, unknown>).summary : JSON.stringify(result);
          pushMessage({ id: crypto.randomUUID(), role: "tool", content: `${name}: ${summary}`, toolResult: result, ts: Date.now() });
        },
        onViewer: (v) => setViewer(v ?? null),
        onDone: (runId) => { if (runId) setActiveRunId(runId); refresh(); },
        onError: (msg) => setError(msg),
      }, controller.signal);
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) setError(String(e));
    } finally {
      clearTimeout(timeoutId);
      abortRef.current = null;
      setStreaming(false);
      incrementChatCount();
      maybeCompoundScienceContext();
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-top">
          <div className="sidebar-brand">
            <img className="sidebar-brand-logo" src={openScienceLogo} alt="OpenScience logo" />
            <span className={`sidebar-brand-dot ${sidecarOnline ? "" : "offline"}`} />
            OpenScience
          </div>

          <button className="new-run-btn" onClick={newConversation}>+ New conversation</button>

          <div className="section-label" style={{ marginTop: 16 }}>
            <IconHistory size={11} style={{ verticalAlign: "middle", marginRight: 4 }} />
            Run history
          </div>
        </div>

        <div className="sidebar-runs">
          <RunHistory runs={runs} selectedId={selectedRunId} onSelect={loadRunIntoChat} />
        </div>

        <div className="sidebar-bottom">
          {compounding && (
            <div style={{ fontSize: 10, color: "#58d4c4", padding: "4px 0", textAlign: "center" }}>
              Compounding science context...
            </div>
          )}
          <button className="btn" onClick={() => setSettingsOpen(true)} style={{ width: "100%" }}>
            <IconSettings size={14} style={{ verticalAlign: "middle", marginRight: 6 }} />
            Settings
          </button>
        </div>
      </aside>

      <main className="main-area">
        <div className="topbar">
          <div className="topbar-status" aria-live="polite">
            <span
              className={`pill ${sidecarOnline ? "badge-pass" : sidecarStarting ? "badge-flag" : "badge-fail"}`}
              title={sidecarOnline ? "Sidecar is running" : sidecarStarting ? "Starting the Python sidecar…" : "Sidecar not reachable"}
            >
              {sidecarOnline ? "sidecar: online" : sidecarStarting ? "sidecar: starting…" : "sidecar: offline"}
            </span>
            <span className="pill">
              <IconBrain size={11} style={{ verticalAlign: "middle", marginRight: 4 }} />
              {config.model}
            </span>
            <span className="pill">
              <IconMicroscope size={11} style={{ verticalAlign: "middle", marginRight: 4 }} />
              {computeBackend}
            </span>
            <select
              value={agent ?? ""}
              onChange={(e) => setAgent(e.target.value || null)}
              title="Specialist agent"
              style={{ background: "transparent", border: "1px solid #1c2230", color: "#9ca3af", borderRadius: 4, padding: "2px 4px", fontSize: 11 }}
            >
              <option value="">no agent</option>
              {agentList.map((a) => <option key={a.name} value={a.name}>{a.name}</option>)}
            </select>
            <select
              value={skill ?? ""}
              onChange={(e) => setSkill(e.target.value || null)}
              title="Reusable skill"
              style={{ background: "transparent", border: "1px solid #1c2230", color: "#9ca3af", borderRadius: 4, padding: "2px 4px", fontSize: 11 }}
            >
              <option value="">no skill</option>
              {skillList.map((s) => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
            {scienceContext && (
              <span className="pill" title="Accumulated science context from prior chats">
                ctx: {Math.round(scienceContext.length / 100) / 10}k
              </span>
            )}
          </div>
          <div>
            <button className="btn" onClick={refresh}>
              <IconRefresh size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
              Refresh
            </button>
          </div>
        </div>

        <div className="workspace">
          <div className="pane">
            <div className="pane-header">Conversation</div>
            <ChatPanel messages={messages} onSend={send} onStop={stop} streaming={streaming} error={error} />
          </div>
          <div className="pane">
            <div className="pane-header" style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <select
                value={selectedRunId ? "inspector" : rightPane}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "inspector" && !selectedRunId) return;
                  if (v !== "inspector") setSelectedRunId(null);
                  setRightPane(v as "viewer" | "manuscript");
                }}
                style={{ background: "transparent", border: "1px solid #1c2230", color: "#9ca3af", borderRadius: 4, padding: "2px 6px", fontSize: 12 }}
              >
                <option value="viewer">Viewer</option>
                <option value="manuscript">Manuscript</option>
                {selectedRunId && <option value="inspector">Run inspector</option>}
              </select>
              {selectedRunId && (
                <button className="btn" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => { setSelectedRunId(null); setRightPane("viewer"); }}>
                  back
                </button>
              )}
            </div>
            {selectedRunId ? (
              rightPane === "manuscript" ? <ManuscriptPanel runId={selectedRunId} /> : <RunInspector runId={selectedRunId} />
            ) : rightPane === "manuscript" ? (
              <ManuscriptPanel runId={activeRunId} />
            ) : (
              <ViewerPanel />
            )}
          </div>
        </div>
      </main>

      {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
