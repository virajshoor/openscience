import { useMemo, useState } from "react";
import {
  IconPlus,
  IconTrash,
  IconArrowUp,
  IconArrowDown,
  IconDownload,
  IconEye,
  IconEdit,
} from "@tabler/icons-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useSession } from "../stores/session";
import { exportManuscript } from "../lib/api";
import { getSidecarUrl } from "../stores/session";
import type { ChatMessage } from "../lib/types";

interface Props {
  runId: string | null;
}

interface FigureRef {
  label: string;
  src: string;
}

/** Scan the conversation for figure artifacts and citation files produced by tools. */
function collectArtifacts(messages: ChatMessage[], runId: string | null) {
  const figures: FigureRef[] = [];
  const bibs: string[] = [];
  for (const m of messages) {
    const result = m.toolResult as Record<string, unknown> | undefined;
    if (!result) continue;
    const view = result["viewer"] as Record<string, unknown> | undefined;
    const views = result["viewers"] as Array<Record<string, unknown>> | undefined;
    const candidates: Array<Record<string, unknown>> = [];
    if (view) candidates.push(view);
    if (Array.isArray(views)) candidates.push(...views);
    for (const v of candidates) {
      if (v && v["type"] === "figure" && typeof v["src"] === "string" && typeof v["label"] === "string") {
        figures.push({ label: v["label"] as string, src: v["src"] as string });
      }
    }
    const data = result["data"] as Record<string, unknown> | undefined;
    if (data && typeof data["file"] === "string") {
      const file = data["file"] as string;
      if (file.startsWith("citations.")) bibs.push(file);
    }
  }
  return { figures, bibs, runId };
}

export default function ManuscriptPanel({ runId }: Props) {
  const sections = useSession((s) => s.manuscript);
  const addSection = useSession((s) => s.addSection);
  const updateSection = useSession((s) => s.updateSection);
  const removeSection = useSession((s) => s.removeSection);
  const moveSection = useSession((s) => s.moveSection);
  const clearManuscript = useSession((s) => s.clearManuscript);
  const messages = useSession((s) => s.messages);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportMsg, setExportMsg] = useState<string | null>(null);
  const [citeKey, setCiteKey] = useState("");

  const { figures, bibs } = useMemo(() => collectArtifacts(messages, runId), [messages, runId]);

  function addSectionFromChat() {
    const last = [...messages].reverse().find((m) => m.role === "assistant" && m.content.trim());
    const id = crypto.randomUUID();
    addSection({
      id,
      title: `Section ${sections.length + 1}`,
      markdown: last ? last.content : "",
    });
    setPreviewId(null);
  }

  function addBlankSection() {
    const id = crypto.randomUUID();
    addSection({ id, title: `Section ${sections.length + 1}`, markdown: "" });
    setPreviewId(null);
  }

  function insertFigure(fig: FigureRef, sectionId: string) {
    const sec = sections.find((s) => s.id === sectionId);
    if (!sec) return;
    const tag = `\n\n![${fig.label}](${fig.src})\n`;
    updateSection(sectionId, { markdown: sec.markdown + tag });
  }

  function insertCitation(sectionId: string) {
    if (!citeKey.trim()) return;
    const sec = sections.find((s) => s.id === sectionId);
    if (!sec) return;
    updateSection(sectionId, { markdown: sec.markdown + ` [@@${citeKey.trim()}]` });
    setCiteKey("");
  }

  function assembledMarkdown(): string {
    return sections
      .map((s) => `# ${s.title}\n\n${s.markdown}`)
      .join("\n\n");
  }

  async function doExport(format: "markdown" | "latex" | "pdf") {
    if (!runId) {
      setExportMsg("Send a message first so a run is active to attach the manuscript to.");
      return;
    }
    setExporting(true);
    setExportMsg(null);
    try {
      let bib: string | undefined;
      if (bibs[0]) {
        try {
          const br = await fetch(`${getSidecarUrl()}/runs/${runId}/outputs/${bibs[0]}`);
          if (br.ok) bib = await br.text();
        } catch { /* best-effort */ }
      }
      const res = await exportManuscript(assembledMarkdown(), format, runId, bib);
      if (res.download) {
        const a = document.createElement("a");
        a.href = `${getSidecarUrl()}/${res.download}`;
        a.download = "";
        a.click();
      }
      setExportMsg(res.warning || (res.ok ? `Exported ${format}.` : res.error || "Export failed."));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="pane-body" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ display: "flex", gap: 8, padding: "8px 12px", borderBottom: "1px solid #1c2230", flexWrap: "wrap", alignItems: "center" }}>
        <button className="btn btn-primary" style={{ padding: "3px 9px", fontSize: 12 }} onClick={addSectionFromChat}>
          <IconPlus size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />From chat
        </button>
        <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} onClick={addBlankSection}>Blank</button>
        <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} onClick={() => clearManuscript()}>Clear</button>
        <div style={{ flex: 1 }} />
        <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} disabled={exporting} onClick={() => doExport("markdown")}>
          <IconDownload size={12} style={{ verticalAlign: "middle", marginRight: 4 }} />.md
        </button>
        <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} disabled={exporting} onClick={() => doExport("latex")}>.tex</button>
        <button className="btn" style={{ padding: "3px 9px", fontSize: 12 }} disabled={exporting} onClick={() => doExport("pdf")}>.pdf</button>
      </div>

      {exportMsg && (
        <div style={{ fontSize: 12, padding: "4px 12px", color: exportMsg.startsWith("Exported") ? "#58d4c4" : "#f0b669" }}>
          {exportMsg}
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
        {sections.length === 0 && (
          <div className="viewer-empty">
            <div className="viewer-empty-icon">📝</div>
            <div>
              No sections yet.<br />
              <span style={{ color: "#4b5563", fontSize: 12 }}>
                Ask the assistant to draft a section, then click "From chat" to pin it here.
                Figures from code.run and citations from crossref.cite can be inserted below.
              </span>
            </div>
          </div>
        )}

        {sections.map((sec, i) => (
          <div key={sec.id} style={{ border: "1px solid #1c2230", borderRadius: 6, padding: 10, background: "#0f1620" }}>
            <div style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 8 }}>
              <input
                value={sec.title}
                onChange={(e) => updateSection(sec.id, { title: e.target.value })}
                style={{ flex: 1, background: "transparent", border: "none", color: "#e5e7eb", fontSize: 14, fontWeight: 600, outline: "none" }}
              />
              <button className="btn" style={{ padding: 2 }} title="Move up" onClick={() => moveSection(sec.id, -1)} disabled={i === 0}><IconArrowUp size={12} /></button>
              <button className="btn" style={{ padding: 2 }} title="Move down" onClick={() => moveSection(sec.id, 1)} disabled={i === sections.length - 1}><IconArrowDown size={12} /></button>
              <button className="btn" style={{ padding: 2 }} title={previewId === sec.id ? "Edit" : "Preview"} onClick={() => setPreviewId(previewId === sec.id ? null : sec.id)}>
                {previewId === sec.id ? <IconEdit size={12} /> : <IconEye size={12} />}
              </button>
              <button className="btn" style={{ padding: 2, color: "#e76e76" }} title="Remove" onClick={() => removeSection(sec.id)}><IconTrash size={12} /></button>
            </div>
            {previewId === sec.id ? (
              <div className="message-markdown" style={{ fontSize: 13, maxHeight: 320, overflow: "auto" }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{sec.markdown}</ReactMarkdown>
              </div>
            ) : (
              <textarea
                value={sec.markdown}
                onChange={(e) => updateSection(sec.id, { markdown: e.target.value })}
                style={{ width: "100%", minHeight: 120, background: "#0b0e14", color: "#e5e7eb", border: "1px solid #1c2230", borderRadius: 4, padding: 8, fontFamily: "monospace", fontSize: 12, resize: "vertical" }}
              />
            )}
            <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
              {figures.length > 0 && (
                <details>
                  <summary style={{ fontSize: 11, color: "#58d4c4", cursor: "pointer" }}>Insert figure ({figures.length})</summary>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 4 }}>
                    {figures.map((f, j) => (
                      <button key={j} className="btn" style={{ padding: "2px 6px", fontSize: 11, textAlign: "left" }} onClick={() => insertFigure(f, sec.id)}>
                        {f.label}
                      </button>
                    ))}
                  </div>
                </details>
              )}
              {bibs.length > 0 && (
                <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                  <input value={citeKey} onChange={(e) => setCiteKey(e.target.value)} placeholder="cite key" style={{ width: 90, fontSize: 11, padding: "2px 4px" }} />
                  <button className="btn" style={{ padding: "2px 6px", fontSize: 11 }} onClick={() => insertCitation(sec.id)}>cite</button>
                  <span style={{ fontSize: 10, color: "#4b5563" }}>bib attached</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}