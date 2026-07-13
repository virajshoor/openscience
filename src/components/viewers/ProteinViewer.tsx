import { useEffect, useRef, useState } from "react";
import { getSidecarUrl } from "../../stores/session";

interface Props {
  src: string;
  label: string;
}

/**
 * 3D protein structure viewer using NGL.
 * Loads .pdb/.cif files from the sidecar's run outputs directory.
 */
export default function ProteinViewer({ src, label }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stage: any = null;
    let cancelled = false;

    async function load() {
      const url = src.startsWith("http") ? src : `${getSidecarUrl()}/${src}`;
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(url, { method: "GET" });
        if (!response.ok) throw new Error(`artifact request failed with HTTP ${response.status}`);
        const module = await import("ngl");
        const NGL = module.default ?? module;
        if (cancelled || !containerRef.current) return;
        if (stageRef.current) stageRef.current.dispose();
        stage = new NGL.Stage(containerRef.current, { backgroundColor: "#0b0e14", quality: "medium" });
        stageRef.current = stage;
        const comp = await stage.loadFile(url);
        comp.addRepresentation("cartoon", { color: "chainid" });
        comp.addRepresentation("licorice", { color: "element", sele: "hetero" });
        comp.autoView();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();

    function onResize() {
      if (stageRef.current) stageRef.current.handleResize();
    }
    window.addEventListener("resize", onResize);

    return () => {
      cancelled = true;
      window.removeEventListener("resize", onResize);
      if (stage) stage.dispose();
    };
  }, [src, label]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "4px 12px", fontSize: 12, color: "#6b7280", borderBottom: "1px solid #1c2230" }}>
        {label} <span style={{ color: "#4b5563" }}>· NGL viewer</span>
      </div>
      {error ? (
        <div className="viewer-empty">Could not load this structure: {error}</div>
      ) : (
        <div ref={containerRef} style={{ flex: 1, minHeight: 300 }} aria-busy={loading} />
      )}
    </div>
  );
}
