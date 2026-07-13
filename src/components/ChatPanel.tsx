import { useEffect, useRef, useState } from "react";
import { useSession } from "../stores/session";
import type { ChatMessage } from "../lib/types";
import { IconPlayerStop, IconSend } from "@tabler/icons-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  messages: ChatMessage[];
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  error: string | null;
}

export default function ChatPanel({ messages, onSend, onStop, streaming, error }: Props) {
  const [input, setInput] = useState("");
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (stickToBottom.current) {
      const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      el.scrollTo({ top: el.scrollHeight, behavior: prefersReduced ? "auto" : "smooth" });
    }
  }, [messages]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }

  function submit() {
    if (!input.trim() || streaming) return;
    onSend(input.trim());
    setInput("");
    setHistoryIndex(null);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKey(e: React.KeyboardEvent) {
    const prompts = messages.filter((m) => m.role === "user").map((m) => m.content);
    if (e.key === "ArrowUp" && !streaming && prompts.length > 0) {
      e.preventDefault();
      const next = historyIndex === null ? prompts.length - 1 : Math.max(0, historyIndex - 1);
      setHistoryIndex(next);
      setInput(prompts[next]);
      requestAnimationFrame(autoGrow);
      return;
    }
    if (e.key === "ArrowDown" && historyIndex !== null) {
      e.preventDefault();
      const next = historyIndex + 1;
      if (next >= prompts.length) {
        setHistoryIndex(null);
        setInput("");
      } else {
        setHistoryIndex(next);
        setInput(prompts[next]);
      }
      requestAnimationFrame(autoGrow);
      return;
    }
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
      <div className="chat-list" ref={scrollRef} onScroll={onScroll} style={{ flex: 1, overflowY: "auto" }}>
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
            {!m.toolCalls?.length && (
              m.role === "assistant" ? (
                m.content ? (
                  <div className="message-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                  </div>
                ) : (streaming ? "…" : "")
              ) : m.content
            )}
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
          onChange={(e) => { setInput(e.target.value); setHistoryIndex(null); autoGrow(); }}
          onKeyDown={handleKey}
          rows={1}
        />
        {streaming ? (
          <button className="btn" onClick={onStop} aria-label="Stop response" title="Stop response">
            <IconPlayerStop size={14} />
          </button>
        ) : (
          <button className="btn btn-primary" onClick={submit} disabled={!input.trim()} aria-label="Send message" title="Send message">
            <IconSend size={14} style={{ verticalAlign: "middle" }} />
          </button>
        )}
      </div>
    </>
  );
}
