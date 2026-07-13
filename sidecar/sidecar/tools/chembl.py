"""ChEMBL tool. Fetches compound and activity data via the ChEMBL webresource client."""

from __future__ import annotations

import httpx

from .registry import tool

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"


@tool(
    "chembl.fetch",
    "Fetch a ChEMBL compound by ID (e.g. CHEMBL192). Returns name, SMILES, molecular formula, weight.",
    {
        "type": "object",
        "properties": {"chembl_id": {"type": "string", "description": "ChEMBL ID, e.g. CHEMBL192"}},
        "required": ["chembl_id"],
    },
)
async def chembl_fetch(chembl_id: str, recorder=None, run_id=None) -> dict:
    headers = {"Accept": "application/json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{CHEMBL_API}/molecule/{chembl_id}.json", headers=headers)
    if r.status_code != 200:
        return {"error": f"ChEMBL {r.status_code}"}
    mol = r.json()
    # ChEMBL nests molecule_properties
    props = mol.get("molecule_properties", {}) or {}
    smiles = (mol.get("molecule_structures", {}) or {}).get("canonical_smiles", "")
    summary = (
        f"ChEMBL {chembl_id}: {mol.get('pref_name', 'unknown')}. "
        f"Formula: {props.get('full_molformula', '?')}. MW: {props.get('full_mwt', '?')}. "
        f"SMILES: {smiles[:60]}{'...' if len(smiles) > 60 else ''}"
    )
    return {
        "summary": summary,
        "data": {
            "chembl_id": chembl_id,
            "name": mol.get("pref_name"),
            "smiles": smiles,
            "formula": props.get("full_molformula"),
            "mol_weight": props.get("full_mwt"),
            "logp": props.get("alogp"),
        },
        "viewer": {"type": "chem", "smiles": smiles, "label": f"ChEMBL {chembl_id}"} if smiles else None,
    }


@tool(
    "chembl.search",
    "Search ChEMBL compounds by name. Returns up to 10 matching ChEMBL IDs.",
    {
        "type": "object",
        "properties": {"name": {"type": "string", "description": "Compound name, e.g. 'aspirin'"}},
        "required": ["name"],
    },
)
async def chembl_search(name: str) -> dict:
    headers = {"Accept": "application/json"}
    params = {"molecule_synonyms": name, "limit": 10, "format": "json"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{CHEMBL_API}/molecule.json", params=params, headers=headers)
    if r.status_code != 200:
        return {"summary": f"ChEMBL search '{name}': no results or error."}
    data = r.json()
    mols = data.get("molecules", [])
    ids = [m.get("molecule_chembl_id") for m in mols]
    summary = f"ChEMBL search '{name}': {len(ids)} hits — {', '.join(ids[:5])}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids)}}