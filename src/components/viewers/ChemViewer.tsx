import { useEffect, useRef, useState } from "react";

interface Props {
  smiles: string;
  label: string;
}

declare global {
  interface Window {
    initRDKitModule?: (wasmPath: string) => Promise<any>;
    RDKit?: any;
  }
}

let rdkitPromise: Promise<any> | null = null;

async function loadRDKit(): Promise<any> {
  if (window.RDKit) return window.RDKit;
  if (rdkitPromise) return rdkitPromise;
  rdkitPromise = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://unpkg.com/@rdkit/rdkit@2024.3.5-1.0.0/Code/MinimalLib/dist/RDKit_minimal.js";
    s.async = true;
    s.onload = async () => {
      try {
        const rdkit = await (window as any).initRDKitModule(
          "https://unpkg.com/@rdkit/rdkit@2024.3.5-1.0.0/Code/MinimalLib/dist/"
        );
        window.RDKit = rdkit;
        resolve(rdkit);
      } catch (e) {
        reject(e);
      }
    };
    s.onerror = () => reject(new Error("Failed to load RDKit"));
    document.head.appendChild(s);
  });
  return rdkitPromise;
}

export default function ChemViewer({ smiles, label }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [errMsg, setErrMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function draw() {
      setStatus("loading");
      try {
        const rdkit = await loadRDKit();
        if (cancelled || !containerRef.current) return;
        const mol = rdkit.get_mol(smiles);
        if (!mol || !mol.is_valid()) {
          setStatus("error");
          setErrMsg("Invalid SMILES");
          if (mol) mol.delete();
          return;
        }
        const svg = mol.get_svg(500, 400);
        mol.delete();
        if (cancelled || !containerRef.current) return;
        const parser = new DOMParser();
        const doc = parser.parseFromString(svg, "image/svg+xml");
        const svgEl = doc.documentElement;
        svgEl.querySelectorAll("script").forEach((n) => n.remove());
        svgEl.removeAttribute("onload");
        svgEl.removeAttribute("onclick");
        containerRef.current.innerHTML = "";
        containerRef.current.appendChild(svgEl);
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setErrMsg(String(e));
      }
    }
    draw();
    return () => { cancelled = true; };
  }, [smiles]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "4px 12px", fontSize: 12, color: "#6b7280", borderBottom: "1px solid #1c2230" }}>
        {label} <span style={{ color: "#4b5563" }}>· RDKit 2D</span>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 14 }}>
        {status === "loading" && <div className="viewer-empty">Loading RDKit...</div>}
        {status === "error" && (
          <div className="viewer-empty">
            <div className="viewer-empty-icon">!</div>
            <div>Failed to render: {errMsg}</div>
            <div style={{ color: "#4b5563", fontSize: 12, fontFamily: "monospace" }}>{smiles}</div>
          </div>
        )}
        <div ref={containerRef} style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: 300 }} />
      </div>
      <div style={{ padding: "8px 14px", fontSize: 11, color: "#4b5563", borderTop: "1px solid #1c2230", fontFamily: "monospace", wordBreak: "break-all" }}>
        {smiles}
      </div>
    </div>
  );
}