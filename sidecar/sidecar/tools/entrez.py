"""NCBI Entrez tool. Fetches sequences and records via the E-utilities API."""

from __future__ import annotations


import httpx

from .registry import tool

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@tool(
    "entrez.search",
    "Search NCBI Entrez databases (e.g. nucleotide, protein, pubmed) by text query. Returns up to 10 IDs.",
    {
        "type": "object",
        "properties": {
            "db": {"type": "string", "description": "NCBI database, e.g. nucleotide, protein, pubmed"},
            "query": {"type": "string", "description": "Search query, e.g. 'BRCA1 human'"},
            "max": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["db", "query"],
    },
)
async def entrez_search(db: str, query: str, max: int = 10) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{EUTILS}/esearch.fcgi",
            params={"db": db, "term": query, "retmax": max, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"Entrez search {r.status_code}"}
    data = r.json().get("esearchresult", {})
    ids = data.get("idlist", [])
    summary = f"Entrez search '{query}' in {db}: {len(ids)} hits — {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids), "db": db}}


@tool(
    "entrez.fetch",
    "Fetch a record from NCBI Entrez by ID. Returns the GenBank/FASTA text.",
    {
        "type": "object",
        "properties": {
            "db": {"type": "string", "description": "NCBI database, e.g. nucleotide"},
            "id": {"type": "string", "description": "Record ID (GI or accession.version)"},
            "rettype": {"type": "string", "description": "Return format, e.g. fasta, gb, docsum"},
        },
        "required": ["db", "id"],
    },
)
async def entrez_fetch(db: str, id: str, rettype: str = "fasta", recorder=None, run_id=None) -> dict:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"{EUTILS}/efetch.fcgi",
            params={"db": db, "id": id, "rettype": rettype, "retmode": "text"},
        )
    if r.status_code != 200:
        return {"error": f"Entrez fetch {r.status_code}"}
    text = r.text
    # Save to outputs
    filename = f"entrez_{db}_{id}.{rettype}"
    output_name = recorder.write_output(run_id, filename, text.encode())
    summary = f"Fetched Entrez {db}/{id} ({rettype}): {len(text)} bytes saved to {output_name}."
    return {
        "summary": summary,
        "data": {"db": db, "id": id, "rettype": rettype, "file": output_name, "size": len(text)},
    }
