"""ClinVar tool. Search and fetch clinical variant records via NCBI E-utilities.

No API key required (NCBI E-utilities are free; rate-limited).
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@tool(
    "clinvar.search",
    "Search NCBI ClinVar for clinical variants by term. Returns up to 10 ClinVar accession IDs.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term, e.g. 'BRCA1 pathogenic' or 'c.686delA'"},
            "max": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
)
async def clinvar_search(query: str, max: int = 10) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "clinvar", "term": query, "retmax": max, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"ClinVar search {r.status_code}"}
    data = r.json().get("esearchresult", {})
    ids = data.get("idlist", [])
    summary = f"ClinVar search '{query}': {len(ids)} hits — {', '.join(ids[:5])}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids)}}


@tool(
    "clinvar.fetch",
    "Fetch a ClinVar variant record by accession ID. Returns the variant summary text.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "ClinVar accession, e.g. VCV000009366"},
        },
        "required": ["id"],
    },
)
async def clinvar_fetch(id: str, recorder=None, run_id=None) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/esummary.fcgi",
            params={"db": "clinvar", "id": id, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"ClinVar fetch {r.status_code}"}
    text = r.text
    output_name = recorder.write_output(run_id, f"clinvar_{id}.json", text.encode())
    summary = f"Fetched ClinVar {id}: {len(text)} bytes saved to {output_name}."
    return {"summary": summary, "data": {"id": id, "file": output_name, "size": len(text)}}