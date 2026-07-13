import { useEffect, useState } from "react";
import { getSidecarUrl } from "../../stores/session";

interface Props {
  src: string;
  label: string;
}

export default function GenomeViewer({ src, label }: Props) {
  const [seq, setSeq] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const url = src.startsWith("http") ? src : `${getSidecarUrl()}/${src}`;
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const text = await r.text();
        const body = text.split("\n").filter((l) => !l.startsWith(">") && l.trim()).join("");
        if (cancelled) return;
        setSeq(body.toUpperCase());
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [src]);

  if (loading) return <div className="viewer-empty">Loading...</div>;
  if (error) return <div className="viewer-empty">Error: {error}</div>;
  if (!seq) return <div className="viewer-empty">No sequence</div>;

  const nucleotideColors: Record<string, string> = {
    A: "#2fdd66", T: "#e76e76", G: "#f0b669", C: "#58d4c4",
  };

  const visibleSeq = seq.slice(0, 800);
  const charWidth = Math.min(8, Math.max(3, 800 / Math.max(visibleSeq.length, 1)));

  const windowSize = 40;
  const MAX_GC_BARS = 200;
  const totalWindows = Math.ceil(seq.length / windowSize);
  const step = Math.max(1, Math.ceil(totalWindows / MAX_GC_BARS));
  const windows: { pos: number; gc: number }[] = [];
  for (let i = 0; i < totalWindows; i += step) {
    let gcCount = 0;
    let total = 0;
    for (let j = i; j < Math.min(i + step, totalWindows); j++) {
      const start = j * windowSize;
      const end = Math.min(start + windowSize, seq.length);
      const w = seq.slice(start, end);
      gcCount += (w.match(/[GC]/g) || []).length;
      total += w.length;
    }
    windows.push({ pos: i * windowSize, gc: total > 0 ? (gcCount / total) * 100 : 0 });
  }

  return (
    <div style={{ padding: 14, height: "100%", overflow: "auto", display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 4 }}>{label}</div>
        <div style={{ fontSize: 11, color: "#4b5563" }}>
          {seq.length.toLocaleString()} bp · FASTA
        </div>
      </div>

      <div>
        <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.08 }}>
          Nucleotide track
        </div>
        <div style={{ fontFamily: "monospace", fontSize: charWidth, lineHeight: 1.4, wordBreak: "break-all", padding: 8, background: "#0f1620", border: "1px solid #1c2230", borderRadius: 6 }}>
          {visibleSeq.split("").map((n, i) => (
            <span key={i} style={{ color: nucleotideColors[n] || "#6b7280" }}>{n}</span>
          ))}
        </div>
        {seq.length > 800 && (
          <div style={{ fontSize: 11, color: "#4b5563", marginTop: 4 }}>
            Showing first 800 bp of {seq.length.toLocaleString()}.
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: 11, color: "#6b7280", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.08 }}>
          GC content (per {windowSize} bp window{step > 1 ? `, sampled every ${step} windows` : ""})
        </div>
        <svg width="100%" height="80" style={{ background: "#0f1620", border: "1px solid #1c2230", borderRadius: 6 }}>
          {windows.map((w, i) => {
            const barW = 100 / windows.length;
            const barH = (w.gc / 100) * 80;
            return (
              <rect
                key={i}
                x={i * barW + 0.2}
                y={80 - barH}
                width={Math.max(barW - 0.4, 0.5)}
                height={barH}
                fill={w.gc > 60 ? "#f0b669" : w.gc > 40 ? "#58d4c4" : "#2fdd66"}
              />
            );
          })}
        </svg>
      </div>
    </div>
  );
}