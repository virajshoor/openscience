"""PubMed literature tool. Search and fetch abstracts via NCBI E-utilities.

No API key required (free, rate-limited). Results are returned as structured
records and rendered as markdown in the chat.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..http import async_client
from .registry import tool

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@tool(
    "pubmed.search",
    "Search PubMed for research papers by query. Returns up to 10 PMIDs.",
    {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "PubMed search, e.g. 'CRISPR off-target effects'"},
            "max": {"type": "integer", "description": "Max results (default 10)"},
        },
        "required": ["query"],
    },
)
async def pubmed_search(query: str, max: int = 10) -> dict:
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmax": max, "retmode": "json"},
        )
    if r.status_code != 200:
        return {"error": f"PubMed search {r.status_code}"}
    data = r.json().get("esearchresult", {})
    ids = data.get("idlist", [])
    summary = f"PubMed search '{query}': {len(ids)} hits — {', '.join(ids[:5])}"
    return {"summary": summary, "data": {"ids": ids, "count": len(ids)}}


def _parse_article(article: ET.Element) -> dict:
    def text(path: str) -> str | None:
        el = article.find(path)
        return el.text.strip() if el is not None and el.text else None

    pmid = text(".//PMID")
    title = text(".//ArticleTitle")
    journal = text(".//Journal/Title")
    year = text(".//PubDate/Year") or text(".//PubDate/MedlineDate")
    abstract_els = article.findall(".//Abstract/AbstractText")
    abstract = " ".join((a.text or "").strip() for a in abstract_els) if abstract_els else None
    authors = []
    for au in article.findall(".//Author"):
        last = au.findtext("LastName")
        init = au.findtext("Initials")
        if last:
            authors.append(f"{last} {init or ''}".strip())
    doi = None
    for aid in article.findall(".//ArticleId"):
        if aid.get("IdType") == "doi":
            doi = aid.text
    return {
        "pmid": pmid,
        "title": title,
        "authors": authors[:20],
        "journal": journal,
        "year": year,
        "doi": doi,
        "abstract": (abstract or "")[:2000] or None,
    }


@tool(
    "pubmed.fetch",
    "Fetch PubMed abstracts (titles, authors, journal, year, abstract) for up to 10 PMIDs. Returns a markdown bullet list rendered in chat and structured records.",
    {
        "type": "object",
        "properties": {
            "ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of PMIDs (max 10)",
            },
        },
        "required": ["ids"],
    },
)
async def pubmed_fetch(ids: list[str]) -> dict:
    ids = [str(i) for i in ids[:10]]
    if not ids:
        return {"error": "no PMIDs provided"}
    async with async_client(30) as c:
        r = await c.get(
            f"{EUTILS}/efetch.fcgi",
            params={"db": "pubmed", "id": ",".join(ids), "rettype": "abstract", "retmode": "xml"},
        )
    if r.status_code != 200:
        return {"error": f"PubMed fetch {r.status_code}"}
    try:
        root = ET.fromstring(r.text)
    except ET.ParseError:
        return {"error": "PubMed fetch: could not parse response"}
    records = [_parse_article(a) for a in root.findall(".//PubmedArticle")]
    bullets = []
    for rec in records:
        au = ", ".join(rec["authors"][:3]) + (" et al." if len(rec["authors"]) > 3 else "")
        bullets.append(
            f"- **{rec['title'] or 'Untitled'}** — {au} *{rec['journal'] or ''}* ({rec['year'] or ''}) PMID:{rec['pmid']}"
            + (f" doi:{rec['doi']}" if rec["doi"] else "")
            + (f"\n  {rec['abstract'][:280]}…" if rec["abstract"] and len(rec["abstract"]) > 280 else
             (f"\n  {rec['abstract']}" if rec["abstract"] else ""))
        )
    summary = f"Fetched {len(records)} PubMed abstract(s)."
    return {"summary": summary, "data": {"records": records, "count": len(records)}, "markdown": "\n\n".join(bullets)}