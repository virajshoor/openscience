import { useEffect, useRef } from "react";
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

  useEffect(() => {
    let stage: any = null;
    let cancelled = false;

    async function load() {
      // NGL needs a UMD import; we dynamically import it to avoid SSR/issues
      const NGL = (await import("ngl")).default;
      if (cancelled || !containerRef.current) return;
      // Clean previous
      if (stageRef.current) {
        stageRef.current.dispose();
      }
      stage = new NGL.Stage(containerRef.current, {
        backgroundColor: "#0b0e14",
        quality: "medium",
      });
      stageRef.current = stage;
      const url = src.startsWith("http") ? src : `${getSidecarUrl()}/${src}`;
      try {
        const comp = await stage.loadFile(url);
        comp.addRepresentation("cartoon", { color: "chainid" });
        comp.addRepresentation("licorice", { color: "element", sele: "hetero" });
        comp.autoView();
      } catch (e) {
        containerRef.current!.innerHTML = `<div class="viewer-empty">Failed to load ${label}: ${e}</div>`;
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
      <div ref={containerRef} style={{ flex: 1, minHeight: 300 }} />
    </div>
  );
}