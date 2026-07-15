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

### Code execution

| Tool | Description |
|------|-------------|
| `code.run` | Execute Python (or R if `Rscript` is present) on the selected compute backend. Captures stdout/stderr and persists figures saved to `OPENSCIENCE_FIG_DIR` as `figure` viewer artifacts. The executed source is recorded in the run. |

The tool sets `MPLBACKEND=Agg` and points `OPENSCIENCE_FIG_DIR` at a per-run
directory. Ask the model to save figures there, e.g.
`plt.savefig(os.path.join(os.environ['OPENSCIENCE_FIG_DIR'], 'plot.png'))`.
Plotly HTML/PNG exports are also detected.

### Compute management

| Tool | Description |
|------|-------------|
| `compute.run` | Run an arbitrary shell command on the selected backend (local/SSH) and return stdout/stderr. |
| `slurm.submit` | Submit a Slurm batch script on the SSH backend. Returns the job id (non-blocking). |
| `slurm.status` | Poll a Slurm job state (PENDING/RUNNING/COMPLETED/…) on the SSH backend. |
| `slurm.cancel` | Cancel a Slurm job (`scancel`) on the SSH backend. |

Slurm requires the SSH backend — set `compute=ssh` (or `slurm`) in Settings and
configure an SSH connection. See [compute.md](./compute.md).

### Ensembl

| Tool | Description |
|------|-------------|
| `ensembl.lookup` | Look up a human gene by symbol or Ensembl ID. Returns symbol, biotype, chromosome, coordinates. |
| `ensembl.sequence` | Fetch a gene/transcript/protein sequence as FASTA and render it in the genome viewer. |
| `ensembl.variants` | List variants overlapping a genomic region. |

### ClinVar

| Tool | Description |
|------|-------------|
| `clinvar.search` | Search NCBI ClinVar for clinical variants. Returns accession IDs. |
| `clinvar.fetch` | Fetch a ClinVar variant record summary by accession. |

### GEO

| Tool | Description |
|------|-------------|
| `geo.search` | Search NCBI GEO (GDS) for expression datasets. Returns GSE/GDS IDs. |
| `geo.fetch` | Fetch a GEO dataset summary (title, sample count, platform). |

### AlphaFold DB

| Tool | Description |
|------|-------------|
| `alphafold.fetch` | Fetch an AlphaFold predicted structure for a UniProt accession. Downloads the PDB/CIF file and renders it in the 3D protein viewer. |

### Literature (PubMed / Europe PMC)

| Tool | Description |
|------|-------------|
| `pubmed.search` | Search PubMed by query. Returns up to 10 PMIDs. |
| `pubmed.fetch` | Fetch PubMed abstracts (title, authors, journal, year, abstract) for up to 10 PMIDs. |
| `europepmc.search` | Search Europe PMC for papers with abstracts when available. |

### Crossref (citations)

| Tool | Description |
|------|-------------|
| `crossref.fetch` | Fetch publication metadata for a DOI (title, authors, journal, year, type). |
| `crossref.cite` | Format one or more DOIs as a citation file (BibTeX / RIS / CSL-JSON) and save it to run outputs. Used by the manuscript feature for properly cited reports. |

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
| figure   | FigureViewer      | `src`, `label`, `format` (`png`/`svg`/`html`/`jpg`/`pdf`) |

A tool may return a single `viewer` and/or a `viewers` list (e.g. `code.run`
emits one figure viewer per saved figure). The client emits a `viewer` SSE
event for each.