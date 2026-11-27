"""Text normalisation shared by indexing (now) and query parsing (later stages).

The SAME function must be used for documents and for queries, otherwise a query
word would never match the lexicon entry that was created for the document word.

Design decisions
* Lower-case everything and fold accents (e.g. "Erdős" -> "erdos").
* A token is a run of letters/digits.  Hyphens, LaTeX symbols, punctuation split
  tokens, so "Maurer--Cartan" -> "maurer", "cartan" and "$P_n$" -> "p", "n".
* Stop words are NOT removed.  The project spec says a query such as
  "Data structures and Algorithms" must return pages containing all four words,
  including "and".  (Ranking can down-weight them via document frequency.)
* Single-character tokens and absurdly long tokens (>40 chars, usually junk such
  as base64 or URLs) are dropped to keep the lexicon small and clean.
* No stemming, so the lexicon contains real words that also exist in the
  pre-trained embeddings used for semantic search later.
"""

import re
import unicodedata

MIN_TOKEN_LEN = 2
MAX_TOKEN_LEN = 40

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    """Lower-case and strip accents, leaving plain ASCII."""
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii").lower()


def tokenize(text: str) -> list:
    """Split free text (title / abstract / authors / query) into tokens."""
    if not text:
        return []
    return [t for t in _TOKEN_RE.findall(_fold(text))
            if MIN_TOKEN_LEN <= len(t) <= MAX_TOKEN_LEN]


def tokenize_categories(categories: str) -> list:
    """Tokenise an arXiv category string such as ``"cs.GT cs.MA econ.TH"``.

    Every category is kept whole ("cs.gt") so a user can search for it, and its
    top-level archive ("cs") is added too so that searching "math" finds all
    maths papers.
    """
    tokens = []
    for cat in _fold(categories or "").split():
        tokens.append(cat)
        if "." in cat:
            tokens.append(cat.split(".", 1)[0])
    return tokens
