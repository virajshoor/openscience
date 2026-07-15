"""AlphaFold DB tool. Fetches predicted protein structures from the AlphaFold Protein Structure DB.

No authentication required (free public API). The metadata endpoint returns the
authoritative file URLs (correct case + model version) for each prediction; we
download via those URLs and render the structure in the existing 3D protein viewer.
"""

from __future__ import annotations

from ..http import async_client
from .registry import tool

ALPHAFOLD = "https://alphafold.ebi.ac.uk/api"


@tool(
    "alphafold.fetch",
    "Fetch an AlphaFold predicted structure for a UniProt accession. Downloads the PDB "
    "(or CIF) file and renders it in the 3D viewer. Returns model confidence (pLDDT). "
    "Not every UniProt entry has an AlphaFold prediction (e.g. very large proteins); "
    "in that case it returns a clear error.",
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
    headers = {"Accept": "application/json"}

    # 1) Prediction metadata (a list, one entry per fragment F1..Fn).
    async with async_client(30) as c:
        meta_r = await c.get(f"{ALPHAFOLD}/prediction/{acc}", headers=headers)
    if meta_r.status_code != 200:
        return {
            "error": (
                f"AlphaFold has no prediction for {acc} (HTTP {meta_r.status_code}). "
                "Not all UniProt entries are in the AlphaFold DB (very large proteins "
                "are often absent); try a different accession or use pdb.fetch for an "
                "experimental structure."
            )
        }
    try:
        entries = meta_r.json()
    except ValueError:
        entries = None
    if not entries:
        return {
            "error": (
                f"AlphaFold has no prediction for {acc}. Not all UniProt entries are in "
                "the AlphaFold DB (very large proteins are often absent); try a different "
                "accession or use pdb.fetch for an experimental structure."
            )
        }

    entry = entries[0]
    # Pick the file URL from the metadata (authoritative case + version).
    url_key = "pdbUrl" if format == "pdb" else "cifUrl"
    file_url = entry.get(url_key)
    if not file_url:
        return {"error": f"AlphaFold metadata for {acc} had no {format} file URL."}

    # 2) Download the structure file.
    async with async_client(60) as c:
        file_r = await c.get(file_url)
    if file_r.status_code != 200:
        return {"error": f"AlphaFold {acc}: file download HTTP {file_r.status_code}"}

    ext = "cif" if format == "cif" else "pdb"
    output_name = recorder.write_output(run_id, f"alphafold_{acc}.{ext}", file_r.content)
    plddt = entry.get("globalMetricValue")
    description = entry.get("uniprotDescription") or entry.get("gene")
    return {
        "summary": (
            f"AlphaFold structure for {acc}"
            + (f" ({description})" if description else "")
            + f" saved and rendered. Mean pLDDT: {plddt}."
        ),
        "data": {
            "uniprot_acc": acc,
            "file": output_name,
            "format": ext,
            "confidence": plddt,
            "model_entity_id": entry.get("modelEntityId"),
            "description": description,
            "organism": entry.get("organismScientificName"),
        },
        "viewer": {"type": "protein", "src": f"runs/{run_id}/outputs/{output_name}", "label": f"AlphaFold {acc}"},
    }