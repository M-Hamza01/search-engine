"""Reading the arXiv metadata file and storing document metadata.

The Kaggle file ``arxiv-metadata-oversnapshot.json`` is JSON Lines: one JSON object
per line with the fields id, title, authors, categories, update_date, abstract, ...

Two pieces live here:
* ``iter_documents``  - streams clean ``Document`` objects (never loads the whole file)
* ``DocStoreWriter`` / ``DocStoreReader`` - a file-based document table so the search
  stage can fetch title/abstract of any doc id with one seek (no database).
"""

import json
from array import array
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterator, Optional


@dataclass
class Document:
    doc_id: int          # internal dense id 0..N-1 (what the indices use)
    arxiv_id: str        # original id, e.g. "2106.11502"
    title: str
    authors: str
    categories: str
    update_date: str     # "YYYY-MM-DD"
    abstract: str


def clean_text(value) -> str:
    """arXiv fields contain hard line breaks and runs of spaces; collapse them."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def date_ordinal(iso_date: str) -> int:
    """Days since year 1 - a cheap integer for the 'newer paper' boost in ranking.
    Returns 0 for a missing or malformed date."""
    try:
        return date.fromisoformat(iso_date).toordinal()
    except (ValueError, TypeError):
        return 0


def iter_documents(path: str, limit: Optional[int] = None,
                   stats: Optional[Counter] = None, start_id: int = 0) -> Iterator[Document]:
    """Yield cleaned documents from a JSONL file, skipping bad records.

    Skipped (and counted in ``stats``): blank lines, lines that are not valid JSON,
    records without an id or without any title/abstract text, and duplicate ids.
    """
    stats = stats if stats is not None else Counter()
    seen_ids = set()
    next_id = start_id
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if limit is not None and stats["documents"] >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                stats["skipped_malformed"] += 1
                continue
            if not isinstance(rec, dict):
                stats["skipped_malformed"] += 1
                continue

            arxiv_id = clean_text(rec.get("id"))
            title = clean_text(rec.get("title"))
            abstract = clean_text(rec.get("abstract"))
            if not arxiv_id or not (title or abstract):
                stats["skipped_invalid"] += 1
                continue
            if arxiv_id in seen_ids:
                stats["skipped_duplicate"] += 1
                continue
            seen_ids.add(arxiv_id)

            yield Document(
                doc_id=next_id,
                arxiv_id=arxiv_id,
                title=title,
                authors=clean_text(rec.get("authors")),
                categories=clean_text(rec.get("categories")),
                update_date=clean_text(rec.get("update_date")),
                abstract=abstract,
            )
            next_id += 1
            stats["documents"] += 1


# --------------------------------------------------------------- document store
class DocStoreWriter:
    """Appends one JSON line per document to ``docs.jsonl`` and remembers the byte
    offset of every line in ``docs.offsets.bin`` (index = doc_id)."""

    def __init__(self, docs_path: str, offsets_path: str):
        self._f = open(docs_path, "wb")           # binary: offsets must be exact bytes
        self._offsets_path = offsets_path
        self._offsets = array("Q")                # unsigned 64-bit ints
        self._pos = 0

    def add(self, doc: Document, n_tokens: int) -> None:
        record = {
            "doc_id": doc.doc_id,
            "id": doc.arxiv_id,
            "title": doc.title,
            "authors": doc.authors,
            "categories": doc.categories,
            "update_date": doc.update_date,
            "date_ord": date_ordinal(doc.update_date),
            "length": n_tokens,                   # total tokens, for length normalisation
            "abstract": doc.abstract,
        }
        data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self._offsets.append(self._pos)
        self._f.write(data)
        self._pos += len(data)

    def close(self) -> None:
        self._f.close()
        with open(self._offsets_path, "wb") as f:
            self._offsets.tofile(f)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class DocStoreReader:
    """Random access to documents by doc_id: one seek + one readline."""

    def __init__(self, docs_path: str, offsets_path: str):
        self._offsets = array("Q")
        with open(offsets_path, "rb") as f:
            data = f.read()
        self._offsets.frombytes(data)
        self._f = open(docs_path, "rb")

    def __len__(self) -> int:
        return len(self._offsets)

    def get(self, doc_id: int) -> dict:
        self._f.seek(self._offsets[doc_id])
        return json.loads(self._f.readline().decode("utf-8"))

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
