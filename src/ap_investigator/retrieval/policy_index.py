"""Policy retrieval.

`LocalPolicyIndex` — BM25 over policy sections, zero dependencies, used for development,
tests and CI. `AzureSearchPolicyIndex` — same interface over Azure AI Search (free tier),
switched on with AP_SEARCH_ENDPOINT (week 5 of the plan). Each chunk is one policy section,
so a hit can be cited exactly as "AP-POL-01 §2.2".
"""

from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from ..config import policy_dir

_DOC_RE = re.compile(r"^#\s+(?P<id>AP-[A-Z]+-\d+)\s+(?P<title>.+)$", re.M)
_SEC_RE = re.compile(r"^##\s+(?P<sec>§\d+\.\d+)\s+(?P<title>.+)$", re.M)
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_STOP = set("a an the and or of to in on for is are be by with from at as it its this that may must not no any "
            "when if until than then into only all each per who which their there".split())


@dataclass(frozen=True)
class PolicySection:
    section_id: str      # "AP-POL-01 §2.2"
    doc_id: str
    doc_title: str
    title: str
    text: str


def load_sections(directory: Path | None = None) -> list[PolicySection]:
    out = []
    for path in sorted((directory or policy_dir()).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        m = _DOC_RE.search(raw)
        if not m:
            continue
        doc_id, doc_title = m["id"], m["title"].strip()
        heads = list(_SEC_RE.finditer(raw))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(raw)
            body = raw[h.end():end].strip()
            out.append(PolicySection(f"{doc_id} {h['sec']}", doc_id, doc_title, h["title"].strip(), body))
    return out


def _tokens(text: str) -> list[str]:
    toks = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]
    # light stemming so "invoiced"/"invoices" meet "invoice"
    return [re.sub(r"(ing|ed|es|s)$", "", t) if len(t) > 4 else t for t in toks]


class PolicyIndex(Protocol):
    def search(self, query: str, top: int = 3) -> list[dict]: ...
    def get(self, section_id: str) -> PolicySection | None: ...


class LocalPolicyIndex:
    def __init__(self, sections: list[PolicySection] | None = None, k1: float = 1.4, b: float = 0.75):
        self.sections = sections if sections is not None else load_sections()
        self.by_id = {s.section_id: s for s in self.sections}
        self.k1, self.b = k1, b
        self.docs = [_tokens(f"{s.doc_title} {s.title} {s.title} {s.text}") for s in self.sections]
        self.tf = [Counter(d) for d in self.docs]
        self.avgdl = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, top: int = 3) -> list[dict]:
        q = _tokens(query)
        scored = []
        for i, tf in enumerate(self.tf):
            dl = len(self.docs[i])
            s = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
                    for t in q if t in tf)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        return [self._hit(self.sections[i], s) for s, i in scored[:top]]

    def get(self, section_id: str) -> PolicySection | None:
        return self.by_id.get(section_id)

    @staticmethod
    def _hit(sec: PolicySection, score: float) -> dict:
        return {"section_id": sec.section_id, "policy": sec.doc_title, "title": sec.title,
                "text": sec.text, "score": round(score, 3)}


class AzureSearchPolicyIndex:
    """Azure AI Search (hybrid-capable) over the same section chunks. Keyless auth.

    Index schema: id (key), section_id, doc_id, doc_title, title, text. Ingest with
    `python -m ap_investigator.retrieval.ingest` (see docs/plan.md, week 5).
    """

    def __init__(self, endpoint: str, index_name: str = "ap-policies"):
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient

        self.client = SearchClient(endpoint, index_name, DefaultAzureCredential())
        self._local = LocalPolicyIndex()  # for get(): section text is versioned in git anyway

    def search(self, query: str, top: int = 3) -> list[dict]:
        hits = self.client.search(search_text=query, top=top)
        return [{"section_id": h["section_id"], "policy": h["doc_title"], "title": h["title"], "text": h["text"],
                 "score": round(h["@search.score"], 3)} for h in hits]

    def get(self, section_id: str) -> PolicySection | None:
        return self._local.get(section_id)


@lru_cache(maxsize=1)
def policy_index() -> PolicyIndex:
    endpoint = os.getenv("AP_SEARCH_ENDPOINT")
    return AzureSearchPolicyIndex(endpoint) if endpoint else LocalPolicyIndex()
