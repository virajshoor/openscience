"""RCSB PDB tool. Fetches 3D structures and metadata."""

from __future__ import annotations

import os

import httpx

from .registry import tool

RCSB_API = "https://data.rcsb.org/rest/v1"
RCSB_FILES = "https://files.rcsb.org/download"


@tool(
    "pdb.fetch",
    "Fetch a PDB structure by 4-character ID (e.g. 1CRN). Downloads the .pdb file and writes it to the run's outputs directory, then signals the 3D protein viewer.",
    {
        "type": "object",
        "properties": {
            "pdb_id": {"type": "string", "description": "4-character PDB ID, e.g. 1CRN"},
            "format": {"type": "string", "enum": ["pdb", "cif"], "description": "File format (default pdb)"},
        },
        "required": ["pdb_id"],
    },
)
async def pdb_fetch(pdb_id: str, format: str = "pdb", recorder=None, run_id=None) -> dict:
    pdb_id = pdb_id.upper()
    async with httpx.AsyncClient(timeout=60) as c:
        # Metadata
        meta_r = await c.get(f"{RCSB_API}/core/entry/{pdb_id}")
        meta = meta_r.json() if meta_r.status_code == 200 else {}
        # File
        ext = "pdb" if format == "pdb" else "cif"
        file_r = await c.get(f"{RCSB_FILES}/{pdb_id}.{ext}")
    if file_r.status_code != 200:
        return {"error": f"PDB file {pdb_id}: HTTP {file_r.status_code}"}
    # Write to run outputs
    filename = f"{pdb_id}.{ext}"
    path = recorder.write_output(run_id, filename, file_r.content)
    return {
        "summary": f"Fetched PDB {pdb_id}: {meta.get('struct', {}).get('title', 'unknown')}. Resolution: {meta.get('rcsb_entry_info', {}).get('resolution_combined', [None])[0]} Å. File saved and rendered in 3D viewer.",
        "data": {
            "pdb_id": pdb_id,
            "title": meta.get("struct", {}).get("title"),
            "resolution": meta.get("rcsb_entry_info", {}).get("resolution_combined"),
            "method": meta.get("rcsb_entry_info", {}).get("experimental_methods"),
            "file": filename,
        },
        "viewer": {"type": "protein", "src": f"runs/{run_id}/outputs/{filename}", "label": f"PDB {pdb_id}"},
    }


@tool(
    "pdb.search",
    "Search RCSB PDB by text query. Returns up to 10 matching PDB IDs.",
    {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Free-text search, e.g. 'hemoglobin'"}},
        "required": ["query"],
    },
)
async def pdb_search(query: str) -> dict:
    body = {
        "query": {
            "type": "terminal",
            "service": "full_text",
            "parameters": {"value": query},
        },
        "return_type": "entry",
        "request_options": {"paginate": {"start": 0, "rows": 10}},
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://search.rcsb.org/rcsbsearch/v2/query", json=body)
    if r.status_code != 200:
        return {
            "error": f"PDB search failed with HTTP {r.status_code}",
            "summary": f"PDB search for '{query}' failed with HTTP {r.status_code}.",
        }
    data = r.json()
    hits = data.get("result_set", [])
    ids = [h.get("identifier") for h in hits]
    summary = f"PDB search '{query}': {len(ids)} hits — {', '.join(ids[:5])}{'...' if len(ids) > 5 else ''}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids)}}
