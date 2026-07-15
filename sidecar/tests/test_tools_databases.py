"""Tests for the new database/literature/citation tools, using mocked HTTP (no network)."""

import httpx
import pytest

from sidecar.repro.recorder import Recorder
from sidecar.tools import alphafold, clinvar, crossref, ensembl, europepmc, geo, pubmed


def _mock_async_client(handler, monkeypatch, modules):
    """Patch async_client in each given module to return a MockTransport-backed client."""

    def factory(timeout):
        transport = httpx.MockTransport(handler)
        return httpx.AsyncClient(transport=transport, timeout=timeout)

    for mod in modules:
        monkeypatch.setattr(mod, "async_client", factory)


@pytest.fixture
def recorder(tmp_path, monkeypatch):
    monkeypatch.setenv("OS_RUNS_DIR", str(tmp_path / "runs"))
    return Recorder(str(tmp_path / "runs"))


@pytest.mark.asyncio
async def test_ensembl_lookup(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "rest.ensembl.org" in str(request.url)
        return httpx.Response(200, json={
            "display_name": "BRCA1", "id": "ENSG00000012048", "biotype": "protein_coding",
            "seq_region_name": "17", "start": 43044295, "end": 43125482, "strand": -1,
            "description": "BRCA1",
        })

    _mock_async_client(handler, monkeypatch, [ensembl])
    r = await ensembl.ensembl_lookup("BRCA1")
    assert r["data"]["symbol"] == "BRCA1"
    assert r["data"]["ensembl_id"] == "ENSG00000012048"


@pytest.mark.asyncio
async def test_ensembl_sequence_emits_genome_viewer(monkeypatch, recorder):
    fasta = ">ENSG00000012048 dna\nATGCATGC\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fasta, headers={"Content-Type": "text/x-fasta"})

    _mock_async_client(handler, monkeypatch, [ensembl])
    run_id = recorder.start({"model": "t"})
    r = await ensembl.ensembl_sequence("ENSG00000012048", recorder=recorder, run_id=run_id)
    assert r["viewer"]["type"] == "genome"
    assert r["viewer"]["src"].startswith(f"runs/{run_id}/outputs/")


@pytest.mark.asyncio
async def test_alphafold_fetch_emits_protein_viewer(monkeypatch, recorder):
    metadata = [{
        "modelEntityId": "AF-P12345-F1",
        "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P12345-F1-model_v6.pdb",
        "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-P12345-F1-model_v6.cif",
        "globalMetricValue": 94.12,
        "uniprotDescription": "Test protein",
        "organismScientificName": "Homo sapiens",
    }]
    pdb_bytes = b"ATOM      1  N   ALA A   1      11.000  12.000  13.000  1.00 20.00           N"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/prediction/P12345"):
            return httpx.Response(200, json=metadata)
        # file download
        return httpx.Response(200, content=pdb_bytes)

    _mock_async_client(handler, monkeypatch, [alphafold])
    run_id = recorder.start({"model": "t"})
    r = await alphafold.alphafold_fetch("P12345", recorder=recorder, run_id=run_id)
    assert r["viewer"]["type"] == "protein"
    assert r["data"]["confidence"] == 94.12
    assert r["data"]["model_entity_id"] == "AF-P12345-F1"


@pytest.mark.asyncio
async def test_alphafold_fetch_missing_prediction(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        # AlphaFold DB returns 404 + empty body for accessions it doesn't have.
        return httpx.Response(404, json={})

    _mock_async_client(handler, monkeypatch, [alphafold])
    r = await alphafold.alphafold_fetch("Q8WZ42")
    assert "error" in r
    assert "no prediction" in r["error"].lower()


@pytest.mark.asyncio
async def test_pubmed_fetch_parses_abstracts(monkeypatch):
    xml = """<PubmedArticleSet>
      <PubmedArticle>
        <MedlineCitation>
          <PMID>123</PMID>
          <Article>
            <ArticleTitle>CRISPR off-target</ArticleTitle>
            <Journal><Title>Nature</Title></Journal>
            <Abstract><AbstractText>Important findings.</AbstractText></Abstract>
            <AuthorList><Author><LastName>Doe</LastName><Initials>J</Initials></Author></AuthorList>
          </Article>
        </MedlineCitation>
      </PubmedArticle>
    </PubmedArticleSet>"""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml, headers={"Content-Type": "application/xml"})

    _mock_async_client(handler, monkeypatch, [pubmed])
    r = await pubmed.pubmed_fetch(["123"])
    assert r["data"]["count"] == 1
    rec = r["data"]["records"][0]
    assert rec["title"] == "CRISPR off-target"
    assert rec["abstract"] == "Important findings."
    assert rec["pmid"] == "123"


@pytest.mark.asyncio
async def test_europepmc_search(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"resultList": {"result": [
            {"pmid": "1", "doi": "10.1/x", "title": "Paper", "authorString": "Doe J, Roe A",
             "journalTitle": "Cell", "pubYear": "2024", "abstractText": "abs"},
        ]}})

    _mock_async_client(handler, monkeypatch, [europepmc])
    r = await europepmc.europepmc_search("single cell")
    assert r["data"]["count"] == 1
    assert r["data"]["records"][0]["title"] == "Paper"


@pytest.mark.asyncio
async def test_crossref_cite_bibtex(monkeypatch, recorder):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "transform/application/x-bibtex" in request.url.path
        return httpx.Response(200, text="@article{Doe2024,\n  title={Paper},\n}")

    _mock_async_client(handler, monkeypatch, [crossref])
    run_id = recorder.start({"model": "t"})
    r = await crossref.crossref_cite(["10.1/x"], recorder=recorder, run_id=run_id)
    assert r["data"]["count"] == 1
    assert r["data"]["file"].endswith(".bib")
    body = (recorder.runs_dir / run_id / "outputs" / r["data"]["file"]).read_text()
    assert "@article" in body


@pytest.mark.asyncio
async def test_crossref_fetch_metadata(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {
            "title": ["A Great Paper"], "author": [{"given": "J", "family": "Doe"}],
            "container-title": ["Nature"], "published-print": {"date-parts": [[2024]]},
            "type": "journal-article",
        }})

    _mock_async_client(handler, monkeypatch, [crossref])
    r = await crossref.crossref_fetch("10.1/x")
    assert r["data"]["title"] == "A Great Paper"
    assert r["data"]["year"] == 2024


@pytest.mark.asyncio
async def test_clinvar_search(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "clinvar" in request.url.params.get("db", "")
        return httpx.Response(200, json={"esearchresult": {"idlist": ["VCV1", "VCV2"]}})

    _mock_async_client(handler, monkeypatch, [clinvar])
    r = await clinvar.clinvar_search("BRCA1 pathogenic")
    assert r["data"]["ids"] == ["VCV1", "VCV2"]


@pytest.mark.asyncio
async def test_geo_search(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"esearchresult": {"idlist": ["2001", "2002"]}})

    _mock_async_client(handler, monkeypatch, [geo])
    r = await geo.geo_search("breast cancer")
    assert r["data"]["count"] == 2