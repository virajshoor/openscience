import { useEffect, useState } from "react";
import { fetchRun, reviewRun, exportRun } from "../lib/api";
import type { RunDetail } from "../lib/types";

interface Props {
  runId: string;
}

export default function RunInspector({ runId }: Props) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await fetchRun(runId);
      setRun(r);
    } catch (e) {
      setRun(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [runId]);

  async function doReview() {
    setReviewing(true);
    try {
      await reviewRun(runId);
      await load();
    } finally {
      setReviewing(false);
    }
  }

  async function doExport() {
    try {
      await exportRun(runId);
    } catch (e) {
      // ignore
    }
  }

  if (loading) return <div className="inspector-empty">Loading run...</div>;
  if (!run) return <div className="inspector-empty">Run not found.</div>;

  const verdict = (run.review as any)?.verdict;
  const issues = (run.review as any)?.issues || [];
  const summary = (run.review as any)?.summary;

  return (
    <div className="pane-body">
      <div className="inspector-section">
        <h4>Run ID</h4>
        <pre style={{ maxHeight: "none" }}>{runId}</pre>
      </div>

      <div className="inspector-section">
        <h4>Manifest</h4>
        <pre>{JSON.stringify(run.manifest, null, 2)}</pre>
      </div>

      <div className="inspector-section">
        <h4>Outputs ({run.outputs?.length ?? 0})</h4>
        <pre>{(run.outputs ?? []).join("\n")}</pre>
      </div>

      <div className="inspector-section">
        <h4>Automated review</h4>
        {!run.review && (
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, color: "#6b7280" }}>Not yet reviewed.</span>
            <button className="btn btn-primary" onClick={doReview} disabled={reviewing}>
              {reviewing ? "Reviewing..." : "Run reviewer"}
            </button>
          </div>
        )}
        {verdict && (
          <>
            <div style={{ marginBottom: 8 }}>
              <span className={`badge badge-${verdict === "pass" ? "pass" : verdict === "fail" ? "fail" : verdict === "flag" ? "flag" : "none"}`}>
                {verdict}
              </span>
            </div>
            {summary && <div style={{ fontSize: 13, marginBottom: 8 }}>{summary}</div>}
            {issues.length > 0 && (
              <pre>{JSON.stringify(issues, null, 2)}</pre>
            )}
          </>
        )}
      </div>

      <div className="inspector-section">
        <h4>Conversation</h4>
        <pre style={{ maxHeight: 400 }}>{JSON.stringify(run.conversation, null, 2)}</pre>
      </div>

      <div className="inspector-section">
        <button className="btn" onClick={doExport}>Export run as JSON</button>
      </div>
    </div>
  );
}