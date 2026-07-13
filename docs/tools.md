# Tools

Tools are the scientific data connectors that the LLM can invoke during a chat.
Each tool is an async Python function decorated with `@tool` that auto-registers
with the global registry.

## Available tools

### UniProt

| Tool | Description |
|------|-------------|
| `uniprot.fetch` | Fetch a UniProt entry by accession (e.g. P12345). Returns annotation data. |

### RCSB PDB

| Tool | Description |
|------|-------------|
| `pdb.fetch` | Fetch a PDB structure by 4-character ID. Downloads the .pdb file, writes it to run outputs, and signals the 3D protein viewer. |
| `pdb.search` | Search RCSB PDB by full-text query. Returns up to 10 matching PDB IDs. |

### NCBI Entrez

| Tool | Description |
|------|-------------|
| `entrez.search` | Search NCBI databases (nucleotide, protein, pubmed) by text query. Returns up to 10 IDs. |
| `entrez.fetch` | Fetch a record from NCBI Entrez by ID. Returns GenBank/FASTA text and saves to run outputs. |

### ChEMBL

| Tool | Description |
|------|-------------|
| `chembl.fetch` | Fetch a ChEMBL compound by ID (e.g. CHEMBL192). Returns name, SMILES, formula, weight. Signals the RDKit chemistry viewer. |
| `chembl.search` | Search ChEMBL compounds by name. Returns up to 10 matching ChEMBL IDs. |

## Adding a custom tool

1. Create a file in `sidecar/sidecar/tools/` (e.g. `my_tool.py`).
2. Import the registry decorator and define your tool:

```python
from .registry import tool

@tool(
    "my_tool.do_thing",
    "Does the thing to X.",
    {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
    },
)
async def do_thing(x: str, recorder=None, run_id=None) -> dict:
    return {"summary": f"Did thing to {x}.", "data": {"x": x}}
```

3. Import the module in `sidecar/sidecar/server.py` lifespan so it registers:

```python
from .tools import my_tool  # noqa: F401
```

4. If your tool produces a viewer artifact, include a `viewer` field:

```python
return {
    "summary": "...",
    "viewer": {"type": "protein", "src": f"runs/{run_id}/outputs/file.pdb", "label": "My Structure"},
}
```

## Tool name convention

Tool names use dot notation (e.g. `pdb.fetch`) internally and in run records.
When sent to the OpenAI API, dots are converted to underscores (e.g. `pdb_fetch`)
because the API requires `^[a-zA-Z0-9_-]+$`. The sidecar maps them back for dispatch.

## Viewer types

| Type     | Renderer          | Required fields        |
|----------|-------------------|------------------------|
| protein  | NGL Viewer        | `src`, `label`         |
| genome   | FASTA + GC tracks | `src`, `label`         |
| chem     | RDKit-JS          | `smiles`, `label`      |