"""Inspect a built index from the command line (handy for the viva demo).

    python -m indexer.lookup --index-dir index_data --word algebraic
    python -m indexer.lookup --index-dir index_data --and data structures algorithms
    python -m indexer.lookup --index-dir index_data --doc 0

``--and`` is only a tiny demonstration that the indices work: it intersects the
sorted posting lists of the query words.  The real search/ranking comes in later stages.
"""

import argparse
import os

from . import config
from .corpus import DocStoreReader
from .inverted_index import InvertedIndexReader
from .lexicon import Lexicon
from .tokenizer import tokenize


def intersect_sorted(a: list, b: list) -> list:
    """Intersection of two ascending lists in O(len(a) + len(b)) (two pointers)."""
    i = j = 0
    out = []
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            out.append(a[i]); i += 1; j += 1
        elif a[i] < b[j]:
            i += 1
        else:
            j += 1
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index-dir", default="index_data")
    ap.add_argument("--word", help="show the postings of one word")
    ap.add_argument("--and", dest="and_words", nargs="+", help="docs containing ALL these words")
    ap.add_argument("--doc", type=int, help="show a document by internal id")
    ap.add_argument("--show", type=int, default=5, help="max documents to print")
    args = ap.parse_args(argv)

    p = lambda name: os.path.join(args.index_dir, name)
    lexicon = Lexicon.load(p(config.LEXICON_FILE))
    docs = DocStoreReader(p(config.DOCS_FILE), p(config.DOCS_OFFSETS_FILE))
    inverted = InvertedIndexReader(p(config.INVERTED_FILE), p(config.INVERTED_OFFSETS_FILE))

    if args.doc is not None:
        d = docs.get(args.doc)
        print(f"[{d['doc_id']}] {d['id']}  {d['title']}\n  {d['authors']}\n  {d['categories']}  {d['update_date']}")

    if args.word:
        for token in tokenize(args.word):
            wid = lexicon.get(token)
            if wid is None:
                print(f"'{token}': not in lexicon")
                continue
            plist = inverted.postings(wid)
            print(f"'{token}': word_id={wid}, document frequency={len(plist)}")
            for doc_id, t, a, ab, c, pos in plist[:args.show]:
                print(f"   doc {doc_id:>6}  title={t} authors={a} abstract={ab} cats={c} first_pos={pos}"
                      f"  | {docs.get(doc_id)['title'][:60]}")

    if args.and_words:
        result = None
        for token in (t for w in args.and_words for t in tokenize(w)):
            wid = lexicon.get(token)
            ids = [post[0] for post in inverted.postings(wid)] if wid is not None else []
            result = ids if result is None else intersect_sorted(result, ids)
        result = result or []
        print(f"{len(result)} documents contain all of {args.and_words}")
        for doc_id in result[:args.show]:
            d = docs.get(doc_id)
            print(f"   doc {doc_id:>6}  {d['id']}  {d['title'][:70]}")


if __name__ == "__main__":
    main()