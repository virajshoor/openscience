import { useEffect, useRef, useState } from "react";
import { useSession } from "../stores/session";
import type { ChatMessage } from "../lib/types";
import { IconSend } from "@tabler/icons-react";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  streaming: boolean;
  error: string | null;
}

export default function ChatPanel({ messages, onSend, streaming, error }: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  function submit() {
    if (!input.trim() || streaming) return;
    onSend(input.trim());
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  function autoGrow() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }

  return (
    <>
      <div className="chat-list" ref={scrollRef} style={{ flex: 1, overflowY: "auto" }}>
        {messages.length === 0 && (
          <div className="viewer-empty">
            <div className="viewer-empty-icon">🧬</div>
            <div>
              Ask anything. Examples:<br />
              <code style={{ color: "#6b7280", fontSize: 12 }}>
                "Fetch UniProt P12345 and find its PDB structures"<br />
                "Show me the 3D structure of 1CRN"<br />
                "Look up aspirin on ChEMBL"
              </code>
            </div>
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="role-tag">{m.role}</div>
            {m.content || (m.role === "assistant" && streaming ? "…" : "")}
            {m.toolCalls && m.toolCalls.length > 0 && (
              <div className="tool-block">
                <div className="tool-block-name">tool call</div>
                {m.toolCalls.map((tc) => (
                  <div key={tc.id}>{tc.name}({JSON.stringify(tc.arguments)})</div>
                ))}
              </div>
            )}
          </div>
        ))}
        {error && (
          <div className="msg tool" style={{ borderColor: "#e76e76" }}>
            <div className="role-tag" style={{ color: "#e76e76" }}>error</div>
            {error}
          </div>
        )}
      </div>
      <div className="chat-composer">
        <textarea
          ref={textareaRef}
          className="chat-input"
          placeholder="Ask a research question…  (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => { setInput(e.target.value); autoGrow(); }}
          onKeyDown={handleKey}
          rows={1}
        />
        <button className="btn btn-primary" onClick={submit} disabled={streaming || !input.trim()}>
          <IconSend size={14} style={{ verticalAlign: "middle" }} />
        </button>
      </div>
    </>
  );
}