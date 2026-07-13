import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, LLMConfig, ViewerArtifact, RunSummary } from "../lib/types";

// Default sidecar URL. When running under Tauri, we'll query the actual port
// via IPC and override this at runtime.
let _sidecarUrl = "http://127.0.0.1:7100";

export function setSidecarUrl(url: string) {
  _sidecarUrl = url;
}

export function getSidecarUrl(): string {
  return _sidecarUrl;
}

export const SIDECAR_URL = _sidecarUrl;

interface SessionState {
  messages: ChatMessage[];
  streaming: boolean;
  viewer: ViewerArtifact | null;
  config: LLMConfig;
  computeBackend: string;
  runs: RunSummary[];
  sidecarOnline: boolean;
  error: string | null;
  setConfig: (c: Partial<LLMConfig>) => void;
  setCompute: (b: string) => void;
  pushMessage: (m: ChatMessage) => void;
  appendAssistant: (id: string, text: string) => void;
  setStreaming: (s: boolean) => void;
  setViewer: (v: ViewerArtifact | null) => void;
  setRuns: (r: RunSummary[]) => void;
  setSidecarOnline: (b: boolean) => void;
  setError: (e: string | null) => void;
  clear: () => void;
}

const defaultConfig: LLMConfig = {
  baseUrl: "https://api.openai.com/v1",
  apiKey: "",
  model: "gpt-4o-mini",
  temperature: 0.2,
  useTools: true,
};

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      messages: [],
      streaming: false,
      viewer: null,
      config: defaultConfig,
      computeBackend: "local",
      runs: [],
      sidecarOnline: false,
      error: null,
      setConfig: (c) => set((s) => ({ config: { ...s.config, ...c } })),
      setCompute: (b) => set({ computeBackend: b }),
      pushMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
      appendAssistant: (id, text) =>
        set((s) => ({
          messages: s.messages.map((m) =>
            m.id === id ? { ...m, content: m.content + text } : m
          ),
        })),
      setStreaming: (b) => set({ streaming: b }),
      setViewer: (v) => set({ viewer: v }),
      setRuns: (r) => set({ runs: r }),
      setSidecarOnline: (b) => set({ sidecarOnline: b }),
      setError: (e) => set({ error: e }),
      clear: () => set({ messages: [], viewer: null, error: null }),
    }),
    {
      name: "openscience-session",
      version: 2,
      migrate: (persisted) => {
        const state = persisted as { config?: Partial<LLMConfig>; computeBackend?: string };
        return {
          config: { ...defaultConfig, ...state.config, apiKey: "" },
          computeBackend: state.computeBackend ?? "local",
        };
      },
      partialize: (s) => ({
        config: { ...s.config, apiKey: "" },
        computeBackend: s.computeBackend,
      }),
    }
  )
);
