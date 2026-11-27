"""Forward index: for each document, the words it contains.

One line per document in ``forward_index.jsonl``::

    {"d": 17, "n": 142, "w": [[wid, tf_title, tf_authors, tf_abstract, tf_cats, first_abs_pos], ...]}

``d`` doc id, ``n`` total token count, ``w`` one entry per DISTINCT word, sorted by
word id.  Its only job is to be the input of the inverted index, but it also lets
the engine re-score a document or remove it later without re-parsing the text.
"""

import json
from typing import Iterator, List, Tuple

from .config import ABSTRACT, AUTHORS, CATEGORIES, NO_POSITION, TITLE
from .corpus import Document
from .lexicon import Lexicon
from .tokenizer import tokenize, tokenize_categories


def analyze_document(doc: Document, lexicon: Lexicon) -> Tuple[int, List[list]]:
    """Turn one document into forward-index entries.

    New words are added to ``lexicon`` on the way (so the lexicon is built in the
    same pass).  Returns ``(total_token_count, entries)``.  This function is also
    what the dynamic-content-addition feature will call for a newly uploaded doc.
    """
    # word_id -> [tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_pos]
    counters = {}

    def count(tokens, field, track_position=False):
        for pos, token in enumerate(tokens):
            wid = lexicon.get_or_add(token)
            c = counters.get(wid)
            if c is None:
                c = counters[wid] = [0, 0, 0, 0, NO_POSITION]
            c[field] += 1
            if track_position and c[4] == NO_POSITION:
                c[4] = pos                      # earliest mention in the abstract

    title_tokens = tokenize(doc.title)
    author_tokens = tokenize(doc.authors)
    abstract_tokens = tokenize(doc.abstract)
    category_tokens = tokenize_categories(doc.categories)

    count(title_tokens, TITLE)
    count(author_tokens, AUTHORS)
    count(abstract_tokens, ABSTRACT, track_position=True)
    count(category_tokens, CATEGORIES)

    n_tokens = len(title_tokens) + len(author_tokens) + len(abstract_tokens) + len(category_tokens)
    entries = [[wid] + c for wid, c in sorted(counters.items())]
    return n_tokens, entries


class ForwardIndexWriter:
    def __init__(self, path: str):
        self._f = open(path, "w", encoding="utf-8", newline="\n")
        self.documents = 0
        self.entries = 0           # total (doc, word) pairs == total postings later

    def write(self, doc_id: int, n_tokens: int, entries: List[list]) -> None:
        line = json.dumps({"d": doc_id, "n": n_tokens, "w": entries}, separators=(",", ":"))
        self._f.write(line + "\n")
        self.documents += 1
        self.entries += len(entries)

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def iter_forward_index(path: str) -> Iterator[Tuple[int, int, List[list]]]:
    """Stream ``(doc_id, n_tokens, entries)`` from a forward index file."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            yield rec["d"], rec["n"], rec["w"]
