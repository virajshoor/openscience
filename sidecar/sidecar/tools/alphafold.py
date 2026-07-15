"""AlphaFold DB tool. Fetches predicted protein structures from the AlphaFold Protein Structure DB.

No authentication required (free public API). Downloads a predicted structure and
renders it in the existing 3D protein viewer.
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

ALPHAFOLD = "https://alphafold.ebi.ac.uk/api"


@tool(
    "alphafold.fetch",
    "Fetch an AlphaFold predicted structure for a UniProt accession. Downloads the PDB file and renders it in the 3D viewer. Returns model confidence (pLDDT) summary.",
    {
        "type": "object",
        "properties": {
            "uniprot_acc": {"type": "string", "description": "UniProt accession, e.g. P12345"},
            "format": {"type": "string", "enum": ["pdb", "cif"], "description": "File format (default pdb)"},
        },
        "required": ["uniprot_acc"],
    },
)
async def alphafold_fetch(uniprot_acc: str, format: str = "pdb", recorder=None, run_id=None) -> dict:
    acc = uniprot_acc.upper()
    async with async_client(60) as c:
        meta_r = await c.get(f"{ALPHAFOLD}/prediction/{acc}")
        meta = meta_r.json() if meta_r.status_code == 200 else {}
        if format == "cif":
            file_r = await c.get(f"{ALPHAFOLD}/entry/{acc}")
        else:
            file_r = await c.get(f"{ALPHAFOLD}/entry-pdb/{acc}")
    if file_r.status_code != 200:
        return {"error": f"AlphaFold {acc}: HTTP {file_r.status_code}"}
    ext = "cif" if format == "cif" else "pdb"
    output_name = recorder.write_output(run_id, f"alphafold_{acc}.{ext}", file_r.content)
    # pLDDT summary from the first (typically only) model
    plddt = None
    if isinstance(meta, list) and meta:
        plddt = meta[0].get("summary", {}).get("modelConfidence")
    elif isinstance(meta, dict):
        plddt = meta.get("summary", {}).get("modelConfidence")
    return {
        "summary": f"AlphaFold structure for {acc} saved and rendered. Confidence: {plddt or 'unknown'}.",
        "data": {"uniprot_acc": acc, "file": output_name, "format": ext, "confidence": plddt},
        "viewer": {"type": "protein", "src": f"runs/{run_id}/outputs/{output_name}", "label": f"AlphaFold {acc}"},
    }