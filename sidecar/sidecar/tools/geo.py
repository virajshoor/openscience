"""GEO (Gene Expression Omnibus) tool. Search and summarize expression datasets via NCBI E-utilities.

No API key required (free, rate-limited).
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@tool(
    "geo.search",
    "Search NCBI GEO (GDS) for expression datasets by term. Returns up to 10 GSE/GDS IDs.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term, e.g. 'breast cancer RNA-seq'"},
            "max": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
)
async def geo_search(query: str, max: int = 10) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "gds", "term": query, "retmax": max, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"GEO search {r.status_code}"}
    data = r.json().get("esearchresult", {})
    ids = data.get("idlist", [])
    summary = f"GEO search '{query}': {len(ids)} hits — {', '.join(ids[:5])}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids)}}


@tool(
    "geo.fetch",
    "Fetch a GEO dataset summary (title, summary, sample count, platform) by GDS/GSE ID.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "GEO dataset ID, e.g. 200000000 or GSE12345"},
        },
        "required": ["id"],
    },
)
async def geo_fetch(id: str) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/esummary.fcgi",
            params={"db": "gds", "id": id, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"GEO fetch {r.status_code}"}
    doc = r.json().get("result", {})
    entry = doc.get(id) if isinstance(doc.get(id), dict) else next(iter(doc.values())) if doc else None
    if not isinstance(entry, dict):
        return {"summary": f"GEO {id}: no summary available."}
    summary = f"GEO {entry.get('entryType', id)}: {entry.get('title', 'untitled')} ({entry.get('n_samples', '?')} samples)."
    return {
        "summary": summary,
        "data": {
            "id": id,
            "title": entry.get("title"),
            "summary": entry.get("summary"),
            "n_samples": entry.get("n_samples"),
            "platform": entry.get("gpl"),
            "type": entry.get("entryType"),
        },
    }