"""Crossref tool. DOI metadata lookup and citation export (BibTeX / RIS / CSL-JSON).

Uses the free Crossref REST API and Crossref content negotiation — no API key
required. `crossref.cite` produces a downloadable citation file in the run
outputs, which the manuscript feature consumes for properly cited reports.
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

CROSSREF = "https://api.crossref.org/works"
UA = "OpenScience/0.2 (https://github.com/virajshoor/openscience; mailto:noreply@openscience.local)"

# Crossref /transform/{content-type} suffixes for direct format export.
FORMAT_SUFFIX = {
    "bibtex": "application/x-bibtex",
    "ris": "application/x-research-info-systems",
    "csl": "application/vnd.citationstyles.csl+json",
}
FORMAT_EXT = {"bibtex": "bib", "ris": "ris", "csl": "json"}


@tool(
    "crossref.fetch",
    "Fetch publication metadata for a DOI from Crossref (title, authors, journal, year, publisher, type).",
    {
        "type": "object",
        "properties": {"doi": {"type": "string", "description": "DOI, e.g. 10.1038/s41586-020-2008-3"}},
        "required": ["doi"],
    },
)
async def crossref_fetch(doi: str) -> dict:
    doi = doi.strip().lower()
    headers = {"User-Agent": UA}
    async with async_client(30) as c:
        r = await c.get(f"{CROSSREF}/{doi}", headers=headers)
    if r.status_code != 200:
        return {"error": f"Crossref {doi}: HTTP {r.status_code}"}
    msg = r.json().get("message", {})
    authors = []
    for a in msg.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)
    title = (msg.get("title") or [""])[0]
    year = None
    for key in ("published-print", "published-online", "issued"):
        dp = msg.get(key, {}).get("date-parts")
        if dp and dp[0]:
            year = dp[0][0]
            break
    summary = f"{title} — {', '.join(authors[:3])}{' et al.' if len(authors) > 3 else ''} ({year}) doi:{doi}"
    return {
        "summary": summary,
        "data": {
            "doi": doi,
            "title": title,
            "authors": authors,
            "journal": (msg.get("container-title") or [None])[0],
            "year": year,
            "publisher": msg.get("publisher"),
            "type": msg.get("type"),
            "url": msg.get("URL"),
        },
    }


@tool(
    "crossref.cite",
    "Format one or more DOIs as a citation file (BibTeX, RIS, or CSL-JSON) and save it to the run outputs. "
    "Use this to build a bibliography for a manuscript.",
    {
        "type": "object",
        "properties": {
            "dois": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of DOIs to cite",
            },
            "format": {
                "type": "string",
                "enum": ["bibtex", "ris", "csl"],
                "description": "Citation format (default bibtex)",
            },
        },
        "required": ["dois"],
    },
)
async def crossref_cite(dois: list[str], format: str = "bibtex", recorder=None, run_id=None) -> dict:
    if recorder is None or run_id is None:
        return {"error": "crossref.cite requires an active run"}
    fmt = format if format in FORMAT_SUFFIX else "bibtex"
    suffix = FORMAT_SUFFIX[fmt]
    headers = {"User-Agent": UA, "Accept": suffix}
    chunks: list[str] = []
    failed: list[str] = []
    for doi in [str(d).strip().lower() for d in dois if str(d).strip()]:
        async with async_client(20) as c:
            r = await c.get(f"{CROSSREF}/{doi}/transform/{suffix}", headers=headers)
        if r.status_code != 200 or not r.text:
            failed.append(doi)
            continue
        text = r.text.strip()
        if fmt == "csl":
            # CSL-JSON is one JSON object per DOI; collect as a JSON array.
            import json
            try:
                chunks.append(json.dumps(json.loads(text)))
            except json.JSONDecodeError:
                chunks.append(text)
        else:
            chunks.append(text)
    if fmt == "csl":
        import json
        body = "[\n" + ",\n".join(chunks) + "\n]" if chunks else "[]"
    else:
        body = "\n\n".join(chunks)
    ext = FORMAT_EXT[fmt]
    output_name = recorder.write_output(run_id, f"citations.{ext}", body.encode())
    summary = f"Saved {len(chunks)} citation(s) as {fmt} to {output_name}."
    if failed:
        summary += f" Failed: {', '.join(failed)}"
    return {
        "summary": summary,
        "data": {"file": output_name, "format": fmt, "count": len(chunks), "failed": failed},
    }