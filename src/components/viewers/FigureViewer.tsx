import { useEffect, useRef, useState } from "react";
import { getSidecarUrl } from "../../stores/session";

interface Props {
  src: string;
  label: string;
  format: "png" | "svg" | "html" | "jpg" | "pdf";
}

function resolveUrl(src: string): string {
  return src.startsWith("http") ? src : `${getSidecarUrl()}/${src}`;
}

/** Strip scripts, event-handler attributes, and javascript: URLs from an SVG/HTML document. */
function sanitize(html: string, mime: "image/svg+xml" | "text/html"): string {
  const doc = new DOMParser().parseFromString(html, mime);
  doc.querySelectorAll("script").forEach((n) => n.remove());
  doc.querySelectorAll("*").forEach((el) => {
    for (const attr of Array.from(el.attributes)) {
      const name = attr.name.toLowerCase();
      if (name.startsWith("on")) {
        el.removeAttribute(attr.name);
      } else if ((name === "href" || name === "src" || name === "xlink:href") &&
        attr.value.trim().toLowerCase().startsWith("javascript:")) {
        el.removeAttribute(attr.name);
      }
    }
  });
  return mime === "image/svg+xml" ? doc.documentElement.outerHTML : doc.body.innerHTML;
}

export default function FigureViewer({ src, label, format }: Props) {
  const url = resolveUrl(src);
  const containerRef = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [errMsg, setErrMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setStatus("loading");
      try {
        if (format === "png" || format === "jpg") {
          if (cancelled) return;
          setStatus("ok");
          return;
        }
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const text = await r.text();
        if (cancelled || !containerRef.current) return;
        if (format === "svg") {
          containerRef.current.innerHTML = sanitize(text, "image/svg+xml");
        } else {
          containerRef.current.innerHTML = "";
        }
        setStatus("ok");
      } catch (e) {
        setStatus("error");
        setErrMsg(String(e));
      }
    }
    if (format === "svg" || format === "html") load();
    else setStatus("ok");
    return () => { cancelled = true; };
  }, [src, format, url]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "4px 12px", fontSize: 12, color: "#6b7280", borderBottom: "1px solid #1c2230", display: "flex", justifyContent: "space-between" }}>
        <span>{label}</span>
        <a href={url} download style={{ color: "#58d4c4", textDecoration: "none", fontSize: 11 }}>download</a>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 14, display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
        {status === "loading" && <div className="viewer-empty">Loading figure...</div>}
        {status === "error" && <div className="viewer-empty">Failed to render: {errMsg}</div>}
        {status === "ok" && (format === "png" || format === "jpg") && (
          <img src={url} alt={label} style={{ maxWidth: "100%", height: "auto" }} />
        )}
        {status === "ok" && format === "svg" && <div ref={containerRef} style={{ width: "100%" }} />}
        {status === "ok" && format === "pdf" && (
          <embed src={url} type="application/pdf" style={{ width: "100%", height: "100%", minHeight: 480 }} />
        )}
        {status === "ok" && format === "html" && (
          <iframe
            title={label}
            src={url}
            sandbox=""
            style={{ width: "100%", height: "100%", minHeight: 480, border: "1px solid #1c2230", borderRadius: 6 }}
          />
        )}
      </div>
    </div>
  );
}