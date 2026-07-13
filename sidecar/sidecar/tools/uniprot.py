"""UniProt tool. Fetches protein entries by accession."""

from __future__ import annotations


from ..http import async_client
from .registry import tool

UNIPROT_API = "https://rest.uniprot.org/uniprotkb"


@tool(
    "uniprot.fetch",
    "Fetch a UniProt protein entry by accession ID (e.g. P12345). Returns name, organism, sequence length, and cross-references to PDB.",
    {
        "type": "object",
        "properties": {
            "accession": {"type": "string", "description": "UniProt accession, e.g. P12345"},
        },
        "required": ["accession"],
    },
)
async def uniprot_fetch(accession: str) -> dict:
    async with async_client(30) as c:
        r = await c.get(f"{UNIPROT_API}/{accession}.json")
    if r.status_code != 200:
        return {"error": f"UniProt {r.status_code}: {r.text[:200]}"}
    data = r.json()
    pdb_refs = [
        x["id"]
        for x in data.get("uniProtKBCrossReferences", [])
        if x.get("database") == "PDB"
    ]
    summary = (
        f"UniProt {accession}: {data.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value', 'unknown')}. "
        f"Organism: {data.get('organism', {}).get('scientificName', 'unknown')}. "
        f"Length: {data.get('sequence', {}).get('length', '?')} aa. "
        f"PDB structures: {', '.join(pdb_refs) if pdb_refs else 'none'}."
    )
    return {
        "summary": summary,
        "data": {
            "accession": accession,
            "name": data.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value"),
            "organism": data.get("organism", {}).get("scientificName"),
            "length": data.get("sequence", {}).get("length"),
            "sequence": data.get("sequence", {}).get("value", "")[:200] + "...",
            "pdb_refs": pdb_refs,
        },
    }
