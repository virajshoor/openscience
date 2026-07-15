"""Europe PMC literature tool. Search papers (with abstracts when available) via the free Europe PMC REST API.

No API key required. A good open alternative/complement to PubMed.
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@tool(
    "europepmc.search",
    "Search Europe PMC for research papers by query. Returns titles, authors, journal, year, DOI, and abstracts when available (up to 10).",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query, e.g. 'single cell RNA-seq brain'"},
            "max": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
)
async def europepmc_search(query: str, max: int = 10) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUROPEPMC}/search",
            params={"query": query, "format": "json", "pageSize": max, "resultType": "core"},
        )
    if r.status_code != 200:
        return {"error": f"Europe PMC search {r.status_code}"}
    data = r.json()
    results = data.get("resultList", {}).get("result", []) or []
    records = []
    for h in results[:max]:
        records.append({
            "pmid": h.get("pmid"),
            "pmcid": h.get("pmcid"),
            "doi": h.get("doi"),
            "title": h.get("title"),
            "authors": (h.get("authorString") or "").split(", ")[:20],
            "journal": h.get("journalTitle"),
            "year": h.get("pubYear"),
            "abstract": (h.get("abstractText") or "")[:2000] or None,
        })
    summary = f"Europe PMC search '{query}': {len(records)} hits."
    return {"summary": summary, "data": {"count": len(records), "records": records}}