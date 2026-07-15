import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { ChatMessage, LLMConfig, ViewerArtifact, RunSummary } from "../lib/types";

let _sidecarUrl = "http://127.0.0.1:7100";

export function setSidecarUrl(url: string) {
  _sidecarUrl = url;
}

export function getSidecarUrl(): string {
  return _sidecarUrl;
}

export const SIDECAR_URL = _sidecarUrl;

export interface ManuscriptSection {
  id: string;
  title: string;
  markdown: string;
}

interface SessionState {
  messages: ChatMessage[];
  streaming: boolean;
  viewer: ViewerArtifact | null;
  config: LLMConfig;
  computeBackend: string;
  runs: RunSummary[];
  sidecarOnline: boolean;
  error: string | null;
  chatCount: number;
  scienceContext: string;
  manuscript: ManuscriptSection[];
  rightPane: "viewer" | "inspector" | "manuscript";
  setConfig: (c: Partial<LLMConfig>) => void;
  setCompute: (b: string) => void;
  pushMessage: (m: ChatMessage) => void;
  appendAssistant: (id: string, text: string) => void;
  setStreaming: (s: boolean) => void;
  setViewer: (v: ViewerArtifact | null) => void;
  setRuns: (r: RunSummary[]) => void;
  setSidecarOnline: (b: boolean) => void;
  setError: (e: string | null) => void;
  incrementChatCount: () => void;
  setScienceContext: (c: string) => void;
  setRightPane: (p: "viewer" | "inspector" | "manuscript") => void;
  addSection: (s: ManuscriptSection) => void;
  updateSection: (id: string, patch: Partial<ManuscriptSection>) => void;
  removeSection: (id: string) => void;
  moveSection: (id: string, dir: -1 | 1) => void;
  clearManuscript: () => void;
  clear: () => void;
}

const defaultConfig: LLMConfig = {
  baseUrl: "https://api.openai.com/v1",
  apiKey: "",
  model: "gpt-5.4-mini",
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
      chatCount: 0,
      scienceContext: "",
      manuscript: [],
      rightPane: "viewer",
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
      incrementChatCount: () => set((s) => ({ chatCount: s.chatCount + 1 })),
      setScienceContext: (c) => set({ scienceContext: c }),
      setRightPane: (p) => set({ rightPane: p }),
      addSection: (sec) => set((s) => ({ manuscript: [...s.manuscript, sec] })),
      updateSection: (id, patch) =>
        set((s) => ({ manuscript: s.manuscript.map((sec) => (sec.id === id ? { ...sec, ...patch } : sec)) })),
      removeSection: (id) => set((s) => ({ manuscript: s.manuscript.filter((sec) => sec.id !== id) })),
      moveSection: (id, dir) =>
        set((s) => {
          const idx = s.manuscript.findIndex((sec) => sec.id === id);
          if (idx < 0) return {};
          const target = idx + dir;
          if (target < 0 || target >= s.manuscript.length) return {};
          const next = [...s.manuscript];
          [next[idx], next[target]] = [next[target], next[idx]];
          return { manuscript: next };
        }),
      clearManuscript: () => set({ manuscript: [] }),
      clear: () => set({ messages: [], viewer: null, error: null }),
    }),
    {
      name: "openscience-session",
      version: 5,
      migrate: (persisted) => {
        const state = persisted as {
          config?: Partial<LLMConfig>;
          computeBackend?: string;
          messages?: ChatMessage[];
          viewer?: ViewerArtifact | null;
          chatCount?: number;
          scienceContext?: string;
          manuscript?: ManuscriptSection[];
          rightPane?: "viewer" | "inspector" | "manuscript";
        };
        return {
          config: { ...defaultConfig, ...state.config, apiKey: "" },
          computeBackend: state.computeBackend ?? "local",
          messages: state.messages ?? [],
          viewer: state.viewer ?? null,
          chatCount: state.chatCount ?? 0,
          scienceContext: state.scienceContext ?? "",
          manuscript: state.manuscript ?? [],
          rightPane: state.rightPane ?? "viewer",
        };
      },
      partialize: (s) => ({
        messages: s.messages.slice(-250).map(({ toolResult: _toolResult, ...message }) => message),
        config: { ...s.config, apiKey: "" },
        computeBackend: s.computeBackend,
        viewer: s.viewer,
        chatCount: s.chatCount,
        scienceContext: s.scienceContext,
        manuscript: s.manuscript,
        rightPane: s.rightPane,
      }),
    }
  )
);
