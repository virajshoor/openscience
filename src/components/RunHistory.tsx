import type { RunSummary } from "../lib/types";

interface Props {
  runs: RunSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function fmtTime(ts: number) {
  const d = new Date(ts * 1000);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString([], { month: "short", day: "numeric" });
}

export default function RunHistory({ runs, selectedId, onSelect }: Props) {
  if (runs.length === 0) {
    return (
      <div style={{ fontSize: 12, color: "#4b5563", padding: "8px 4px" }}>
        No runs yet. Send a message to start.
      </div>
    );
  }
  return (
    <div>
      {runs.map((r) => (
        <div
          key={r.run_id}
          className="run-item"
          onClick={() => onSelect(r.run_id)}
          style={r.run_id === selectedId ? { borderColor: "#2fdd66" } : {}}
        >
          <div className="run-id">{r.run_id}</div>
          <div className="run-meta">
            {fmtTime(r.started_at)} · {r.model ?? "?"}
            {r.review && (
              <span
                className={`badge badge-${r.review === "pass" ? "pass" : r.review === "fail" ? "fail" : r.review === "flag" ? "flag" : "none"}`}
                style={{ marginLeft: 6 }}
              >
                {r.review}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}