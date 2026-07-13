import { useState } from "react";
import { useSession } from "../stores/session";
import { configureSSH, listCompute } from "../lib/api";

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
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Settings</h2>

        <div className="field">
          <label>OpenAI-compatible endpoint</label>
          <input
            value={config.baseUrl}
            onChange={(e) => setConfig({ baseUrl: e.target.value })}
            placeholder="https://api.openai.com/v1"
          />
          <div className="field-hint">
            Any /v1/chat/completions endpoint — OpenAI, Ollama, vLLM, Together, Groq, OpenRouter, etc.
          </div>
        </div>

        <div className="field">
          <label>API key</label>
          <input
            type="password"
            value={config.apiKey}
            onChange={(e) => setConfig({ apiKey: e.target.value })}
            placeholder="sk-…"
          />
        </div>

        <div className="field">
          <label>Model</label>
          <input
            value={config.model}
            onChange={(e) => setConfig({ model: e.target.value })}
            placeholder="gpt-4o-mini"
          />
        </div>

        <div className="field">
          <label>Temperature</label>
          <input
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
            type="checkbox"
            checked={config.useTools}
            onChange={(e) => setConfig({ useTools: e.target.checked })}
          />
          Use native tool-calling (unchecked → ReAct text fallback)
        </label>

        <div style={{ height: 1, background: "#1c2230", margin: "16px 0" }} />

        <div className="field">
          <label>Compute backend</label>
          <select value={computeBackend} onChange={(e) => setCompute(e.target.value)}>
            <option value="local">local</option>
            <option value="ssh">ssh</option>
          </select>
          <div className="field-hint">"ssh" requires configuring an SSH connection below.</div>
        </div>

        <div className="field">
          <label>SSH host</label>
          <input value={sshHost} onChange={(e) => setSshHost(e.target.value)} placeholder="lab-box.university.edu" />
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <div className="field" style={{ flex: 1 }}>
            <label>User</label>
            <input value={sshUser} onChange={(e) => setSshUser(e.target.value)} placeholder="your-username" />
          </div>
          <div className="field" style={{ width: 80 }}>
            <label>Port</label>
            <input value={sshPort} onChange={(e) => setSshPort(e.target.value)} placeholder="22" />
          </div>
        </div>
        <div className="field">
          <label>SSH private key path</label>
          <input value={sshKey} onChange={(e) => setSshKey(e.target.value)} placeholder="~/.ssh/id_rsa" />
        </div>
        {sshMsg && <div className="field-hint" style={{ color: sshMsg.includes("configured") ? "#58d4c4" : "#e76e76" }}>{sshMsg}</div>}

        <div className="settings-actions">
          <button className="btn" onClick={saveSSH}>Save SSH</button>
          <button className="btn btn-primary" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}