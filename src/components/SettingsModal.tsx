import { useEffect, useRef, useState } from "react";
import { useSession } from "../stores/session";
import { configureSSH } from "../lib/api";

interface Props {
  onClose: () => void;
}

export default function SettingsModal({ onClose }: Props) {
  const config = useSession((s) => s.config);
  const setConfig = useSession((s) => s.setConfig);
  const computeBackend = useSession((s) => s.computeBackend);
  const setCompute = useSession((s) => s.setCompute);
  const [sshHost, setSshHost] = useState("");
  const [sshUser, setSshUser] = useState("");
  const [sshPort, setSshPort] = useState("22");
  const [sshKey, setSshKey] = useState("");
  const [sshMsg, setSshMsg] = useState<string | null>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeBtnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeBtnRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, input, select, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  async function saveSSH() {
    setSshMsg(null);
    const ok = await configureSSH(sshHost, sshUser, parseInt(sshPort) || 22, sshKey || undefined);
    if (ok) {
      setCompute("ssh");
      setSshMsg("SSH backend configured.");
    } else {
      setSshMsg("Failed to configure SSH.");
    }
  }

  return (
    <div className="settings-overlay" onClick={onClose} role="presentation">
      <div
        className="settings-modal"
        onClick={(e) => e.stopPropagation()}
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        tabIndex={-1}
      >
        <h2 id="settings-title">Settings</h2>

        <div className="field">
          <label htmlFor="cfg-endpoint">OpenAI-compatible endpoint</label>
          <input
            id="cfg-endpoint"
            value={config.baseUrl}
            onChange={(e) => setConfig({ baseUrl: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
          <div className="field-hint">
            Any /v1/chat/completions endpoint — OpenAI, Ollama, vLLM, Together, Groq, OpenRouter, etc.
          </div>
        </div>

        <div className="field">
          <label htmlFor="cfg-key">API key</label>
          <input
            id="cfg-key"
            type="password"
            value={config.apiKey}
            onChange={(e) => setConfig({ apiKey: e.target.value })}
            placeholder="sk-…"
          />
          <div className="field-hint">Stored in your macOS Keychain. Never written to runs or the repository.</div>
        </div>

        <div className="field">
          <label htmlFor="cfg-model">Model</label>
          <input
            id="cfg-model"
            value={config.model}
            onChange={(e) => setConfig({ model: e.target.value })}
            placeholder="gpt-5.4-mini"
          />
        </div>

        <div className="field">
          <label htmlFor="cfg-temp">Temperature</label>
          <input
            id="cfg-temp"
            type="number"
            step="0.1"
            min="0"
            max="2"
            value={config.temperature}
            onChange={(e) => setConfig({ temperature: parseFloat(e.target.value) })}
          />
        </div>

        <label className="checkbox-row">
          <input
            id="cfg-tools"
            type="checkbox"
            checked={config.useTools}
            onChange={(e) => setConfig({ useTools: e.target.checked })}
          />
          Use native tool-calling (unchecked → ReAct text fallback)
        </label>

        <div style={{ height: 1, background: "#1c2230", margin: "16px 0" }} />

        <div className="field">
          <label htmlFor="cfg-compute">Compute backend</label>
          <select id="cfg-compute" value={computeBackend} onChange={(e) => setCompute(e.target.value)}>
            <option value="local">local</option>
            <option value="ssh">ssh</option>
          </select>
          <div className="field-hint">"ssh" requires configuring an SSH connection below.</div>
        </div>

        <div className="field">
          <label htmlFor="ssh-host">SSH host</label>
          <input id="ssh-host" value={sshHost} onChange={(e) => setSshHost(e.target.value)} placeholder="lab-box.university.edu" />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="ssh-user">User</label>
            <input id="ssh-user" value={sshUser} onChange={(e) => setSshUser(e.target.value)} placeholder="your-username" />
          </div>
          <div className="field" style={{ width: 80 }}>
            <label htmlFor="ssh-port">Port</label>
            <input id="ssh-port" value={sshPort} onChange={(e) => setSshPort(e.target.value)} placeholder="22" />
          </div>
        </div>
        <div className="field">
          <label htmlFor="ssh-key">SSH private key path</label>
          <input id="ssh-key" value={sshKey} onChange={(e) => setSshKey(e.target.value)} placeholder="~/.ssh/id_rsa" />
        </div>
        {sshMsg && <div className="field-hint" style={{ color: sshMsg.includes("configured") ? "#58d4c4" : "#e76e76" }}>{sshMsg}</div>}

        <div className="settings-actions">
          <button className="btn" onClick={saveSSH}>Save SSH</button>
          <button className="btn btn-primary" ref={closeBtnRef} onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}
