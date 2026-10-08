"""Bounded scientific literature retrieval for HDS research workspaces.

Retrieval discovers sources; it does not verify evidence or establish scientific truth.
Only bibliographic metadata and publisher/index abstracts are persisted as unverified
source material. Evidence verification remains a separate governed step.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html import unescape
from uuid import uuid4

from app.evidence_pipeline import EvidencePipeline
from app.models import now


class ScientificRetrievalService:
    PROVIDERS = {"pubmed", "crossref"}

    def __init__(self, db, timeout: float = 20.0):
        self.db = db
        self.timeout = float(timeout)

    def retrieve(self, workspace_id: str, query: str | None = None, providers=("pubmed", "crossref"), limit: int = 20):
        workspace = self.db.one("SELECT * FROM research_workspaces WHERE id=?", (workspace_id,))
        if not workspace:
            raise ValueError("research workspace not found")
        if workspace["status"] != "ACTIVE":
            raise ValueError("research workspace must be ACTIVE")

        q = str(query or workspace["question"]).strip()
        if not q:
            raise ValueError("retrieval query is required")
        limit = max(1, min(int(limit), 50))
        selected = []
        for provider in providers:
            p = str(provider).strip().lower()
            if p in self.PROVIDERS and p not in selected:
                selected.append(p)
        if not selected:
            raise ValueError("at least one supported retrieval provider is required")

        run_id = str(uuid4())
        started = now()
        self.db.execute(
            "INSERT INTO research_retrieval_runs(id,workspace_id,provider,query,status,result_count,created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, workspace_id, ",".join(selected), q, "RUNNING", 0, started),
        )

        all_records = []
        errors = []
        for provider in selected:
            try:
                if provider == "pubmed":
                    records = self._pubmed(q, limit)
                else:
                    records = self._crossref(q, limit)
                all_records.extend((provider, r) for r in records)
            except Exception as exc:
                errors.append(f"{provider}: {exc}")

        # Deduplicate by canonical URL/DOI/PMID while preserving provider provenance.
        seen = set()
        unique = []
        for provider, record in all_records:
            key = str(record.get("url") or record.get("doi") or record.get("record_id") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append((provider, record))
        unique = unique[:limit]

        persisted = 0
        try:
            for rank, (provider, record) in enumerate(unique, start=1):
                source = EvidencePipeline(self.db).register_source(
                    title=record["title"],
                    url=record["url"],
                    authors=record.get("authors", ""),
                    year=record.get("year"),
                    source_type=record.get("source_type", "PAPER"),
                )
                content = record.get("abstract") or ""
                if content:
                    EvidencePipeline(self.db).ingest_text(source["id"], content)

                self.db.execute(
                    """INSERT INTO research_workspace_sources
                       (id,workspace_id,source_id,relevance,notes,content_hash,reviewed,created_at)
                       VALUES (?,?,?,?,?,?,0,?)
                       ON CONFLICT(workspace_id,source_id) DO NOTHING""",
                    (
                        str(uuid4()),
                        workspace_id,
                        source["id"],
                        "DISCOVERED",
                        json.dumps({
                            "retrieval_run_id": run_id,
                            "provider": provider,
                            "provider_record_id": record.get("record_id"),
                            "retrieval_metadata": record,
                            "verified": False,
                        }, sort_keys=True),
                        None,
                        now(),
                    ),
                )
                self.db.execute(
                    """INSERT INTO research_retrieval_results
                       (id,retrieval_run_id,workspace_id,source_id,provider_record_id,rank,metadata,created_at)
                       VALUES (?,?,?,?,?,?,?,?)
                       ON CONFLICT(retrieval_run_id,provider_record_id) DO NOTHING""",
                    (
                        str(uuid4()), run_id, workspace_id, source["id"],
                        str(record.get("record_id") or source["url"]),
                        rank, json.dumps(record, sort_keys=True), now(),
                    ),
                )
                persisted += 1

            status = "COMPLETED" if not errors else ("PARTIAL" if persisted else "FAILED")
            error = "; ".join(errors)[:4000] if errors else None
            self.db.execute(
                "UPDATE research_retrieval_runs SET status=?,result_count=?,error=?,completed_at=? WHERE id=? AND status='RUNNING'",
                (status, persisted, error, now(), run_id),
            )
        except Exception as exc:
            self.db.execute(
                "UPDATE research_retrieval_runs SET status='FAILED',result_count=?,error=?,completed_at=? WHERE id=? AND status='RUNNING'",
                (persisted, str(exc)[:4000], now(), run_id),
            )
            raise

        return {
            "retrieval_run": self.db.one("SELECT * FROM research_retrieval_runs WHERE id=?", (run_id,)),
            "results": self.db.all(
                "SELECT r.*,s.title,s.url,s.authors,s.publication_year,s.source_type FROM research_retrieval_results r JOIN sources s ON s.id=r.source_id WHERE r.retrieval_run_id=? ORDER BY r.rank",
                (run_id,),
            ),
            "errors": errors,
            "scientific_status": "DISCOVERY_ONLY_UNVERIFIED",
        }

    def list_results(self, workspace_id: str):
        if not self.db.one("SELECT id FROM research_workspaces WHERE id=?", (workspace_id,)):
            raise ValueError("research workspace not found")
        return self.db.all(
            """SELECT r.*,s.title,s.url,s.authors,s.publication_year,s.source_type
               FROM research_retrieval_results r
               JOIN sources s ON s.id=r.source_id
               WHERE r.workspace_id=?
               ORDER BY r.created_at DESC,r.rank""",
            (workspace_id,),
        )

    def _request(self, url: str, accept: str):
        headers = {
            "Accept": accept,
            "User-Agent": "HDS-Scientific-Retrieval/1.0 (+https://human-development-science.local)",
        }
        email = os.getenv("HDS_RESEARCH_EMAIL", "").strip()
        if email:
            headers["From"] = email
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            return response.read()

    def _pubmed(self, query: str, limit: int):
        params = urllib.parse.urlencode({
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
        })
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + params
        search_payload = json.loads(self._request(search_url, "application/json").decode("utf-8"))
        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode({
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
        })
        root = ET.fromstring(self._request(fetch_url, "application/xml"))
        records = []
        for article in root.findall(".//PubmedArticle"):
            pmid = self._text(article.find("./MedlineCitation/PMID"))
            title = self._text(article.find("./MedlineCitation/Article/ArticleTitle"))
            abstract_parts = []
            for node in article.findall("./MedlineCitation/Article/Abstract/AbstractText"):
                label = node.attrib.get("Label", "").strip()
                value = self._text(node)
                if value:
                    abstract_parts.append(f"{label}: {value}" if label else value)
            authors = []
            for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
                last = self._text(author.find("LastName"))
                initials = self._text(author.find("Initials"))
                collective = self._text(author.find("CollectiveName"))
                name = collective or " ".join(x for x in (last, initials) if x)
                if name:
                    authors.append(name)
            year = self._pubmed_year(article)
            if not pmid or not title:
                continue
            records.append({
                "record_id": f"pubmed:{pmid}",
                "title": title,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "authors": ", ".join(authors),
                "year": year,
                "abstract": " ".join(abstract_parts),
                "source_type": "PUBMED",
                "provider": "pubmed",
            })
        return records

    def _crossref(self, query: str, limit: int):
        params = urllib.parse.urlencode({
            "query.bibliographic": query,
            "rows": limit,
            "select": "DOI,title,author,published,URL,abstract,type",
        })
        url = "https://api.crossref.org/works?" + params
        payload = json.loads(self._request(url, "application/json").decode("utf-8"))
        records = []
        for item in payload.get("message", {}).get("items", []):
            doi = str(item.get("DOI") or "").strip()
            titles = item.get("title") or []
            title = str(titles[0]).strip() if titles else ""
            if not doi or not title:
                continue
            authors = []
            for author in item.get("author") or []:
                name = " ".join(str(author.get(k) or "").strip() for k in ("given", "family")).strip()
                if name:
                    authors.append(name)
            published = item.get("published-print") or item.get("published-online") or item.get("published") or {}
            parts = published.get("date-parts") or []
            year = int(parts[0][0]) if parts and parts[0] and str(parts[0][0]).isdigit() else None
            abstract = self._clean_markup(str(item.get("abstract") or ""))
            records.append({
                "record_id": f"doi:{doi.lower()}",
                "title": title,
                "url": str(item.get("URL") or f"https://doi.org/{doi}"),
                "authors": ", ".join(authors),
                "year": year,
                "abstract": abstract,
                "source_type": "CROSSREF",
                "provider": "crossref",
            })
        return records

    @staticmethod
    def _text(node):
        if node is None:
            return ""
        return "".join(node.itertext()).strip()

    @staticmethod
    def _pubmed_year(article):
        for path in (
            "./MedlineCitation/Article/Journal/JournalIssue/PubDate/Year",
            "./MedlineCitation/Article/ArticleDate/Year",
        ):
            value = article.find(path)
            if value is not None and (value.text or "").strip().isdigit():
                return int(value.text.strip())
        return None

    @staticmethod
    def _clean_markup(value):
        value = re.sub(r"<[^>]+>", " ", value)
        return unescape(re.sub(r"\s+", " ", value)).strip()
