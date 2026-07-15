"""Ensembl tool. Gene lookup, sequences, and variants via the free Ensembl REST API.

No authentication required (rate-limited public API).
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

ENSEMBL = "https://rest.ensembl.org"


@tool(
    "ensembl.lookup",
    "Look up a human gene by symbol or Ensembl ID via Ensembl. Returns symbol, Ensembl ID, biotype, chromosome, start/end.",
    {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Gene symbol (e.g. BRCA1) or Ensembl gene ID (ENSG00000012048)"},
        },
        "required": ["symbol"],
    },
)
async def ensembl_lookup(symbol: str) -> dict:
    headers = {"Accept": "application/json"}
    if symbol.upper().startswith("ENSG"):
        url = f"{ENSEMBL}/lookup/id/{symbol}?expand=1"
    else:
        url = f"{ENSEMBL}/lookup/symbol/homo_sapiens/{symbol}?expand=1"
    async with async_client(30) as c:
        r = await c.get(url, headers=headers)
    if r.status_code != 200:
        return {"error": f"Ensembl lookup {r.status_code}"}
    g = r.json()
    summary = (
        f"Ensembl {g.get('display_name', symbol)} ({g.get('id')}): {g.get('biotype')} "
        f"on chr {g.get('seq_region_name')}:{g.get('start')}-{g.get('end')} ({g.get('strand')})"
    )
    return {
        "summary": summary,
        "data": {
            "symbol": g.get("display_name"),
            "ensembl_id": g.get("id"),
            "biotype": g.get("biotype"),
            "chr": g.get("seq_region_name"),
            "start": g.get("start"),
            "end": g.get("end"),
            "strand": g.get("strand"),
            "description": g.get("description"),
        },
    }


@tool(
    "ensembl.sequence",
    "Fetch a gene/transcript sequence from Ensembl as FASTA and render it in the genome viewer.",
    {
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Ensembl ID (gene/transcript/protein), e.g. ENSG00000012048 or ENST00000357654"},
            "type": {"type": "string", "enum": ["genomic", "cds", "protein"], "description": "Sequence type (default genomic)"},
        },
        "required": ["id"],
    },
)
async def ensembl_sequence(id: str, type: str = "genomic", recorder=None, run_id=None) -> dict:
    headers = {"Accept": "text/x-fasta"}
    params = {"type": type}
    async with async_client(60) as c:
        r = await c.get(f"{ENSEMBL}/sequence/id/{id}", headers=headers, params=params)
    if r.status_code != 200:
        return {"error": f"Ensembl sequence {r.status_code}"}
    fasta = r.text
    output_name = recorder.write_output(run_id, f"ensembl_{id}_{type}.fasta", fasta.encode())
    header = fasta.splitlines()[0] if fasta else id
    return {
        "summary": f"Fetched Ensembl {type} sequence for {id}: {len(fasta)} bytes.",
        "data": {"id": id, "type": type, "file": output_name, "size": len(fasta), "header": header},
        "viewer": {"type": "genome", "src": f"runs/{run_id}/outputs/{output_name}", "label": f"Ensembl {id}"},
    }


@tool(
    "ensembl.variants",
    "List variants overlapping a genomic region from Ensembl. Returns variant IDs and locations.",
    {
        "type": "object",
        "properties": {
            "region": {"type": "string", "description": "Region e.g. '17:41196312-41277500'"},
        },
        "required": ["region"],
    },
)
async def ensembl_variants(region: str) -> dict:
    headers = {"Accept": "application/json"}
    async with async_client(30) as c:
        r = await c.get(f"{ENSEMBL}/overlap/region/human/{region}?feature=variation", headers=headers)
    if r.status_code != 200:
        return {"error": f"Ensembl variants {r.status_code}"}
    feats = r.json() or []
    variants = [
        {"id": f.get("id"), "start": f.get("start"), "end": f.get("end"), "consequence": f.get("consequence_type")}
        for f in feats[:50]
    ]
    summary = f"Ensembl variants in {region}: {len(variants)} found — {', '.join(v['id'] for v in variants[:5] if v.get('id'))}"
    return {"summary": summary, "data": {"region": region, "count": len(variants), "variants": variants}}