"""Command line entry point: builds lexicon, forward index and inverted index.

    python -m indexer.build_index --input data/sample_arxiv.jsonl --out index_data
    python -m indexer.build_index --input arxiv_subset_75k.jsonl --out index_data

Pipeline (documents are streamed, never all held in memory):
  pass 1  JSONL -> tokens -> lexicon (in RAM, it is small) + docs.jsonl + forward_index.jsonl
  pass 2  forward_index.jsonl -> inverted_index.jsonl   (external sort-merge)
"""

import argparse
import json
import os
import statistics
import time
from collections import Counter

from . import config
from .corpus import DocStoreWriter, iter_documents
from .forward_index import ForwardIndexWriter, analyze_document
from .inverted_index import build_inverted_index
from .lexicon import Lexicon
from .tokenizer import tokenize


def _peak_memory_mb():
    """Peak RSS of this process in MB (not available on Windows -> None)."""
    try:
        import resource
        import sys
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1)
    except ImportError:
        return None


def build(input_path: str, out_dir: str, limit=None, batch_docs: int = 5000) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    path = lambda name: os.path.join(out_dir, name)
    skip_stats = Counter()
    lexicon = Lexicon()
    abstract_word_counts = []
    total_tokens = 0

    # ---------------- pass 1: lexicon + document store + forward index
    t0 = time.perf_counter()
    with DocStoreWriter(path(config.DOCS_FILE), path(config.DOCS_OFFSETS_FILE)) as docs, \
            ForwardIndexWriter(path(config.FORWARD_FILE)) as forward:
        for doc in iter_documents(input_path, limit=limit, stats=skip_stats):
            n_tokens, entries = analyze_document(doc, lexicon)
            docs.add(doc, n_tokens)
            forward.write(doc.doc_id, n_tokens, entries)
            abstract_word_counts.append(len(tokenize(doc.abstract)))
            total_tokens += n_tokens
        n_docs, forward_entries = forward.documents, forward.entries
    lexicon.save(path(config.LEXICON_FILE))
    t1 = time.perf_counter()

    # ---------------- pass 2: inverted index
    inv = build_inverted_index(path(config.FORWARD_FILE), path(config.INVERTED_FILE),
                               path(config.INVERTED_OFFSETS_FILE), vocab_size=len(lexicon),
                               batch_docs=batch_docs, tmp_dir=out_dir)
    t2 = time.perf_counter()

    stats = {
        "input": os.path.abspath(input_path),
        "documents": n_docs,
        "skipped_malformed": skip_stats["skipped_malformed"],
        "skipped_invalid": skip_stats["skipped_invalid"],
        "skipped_duplicate": skip_stats["skipped_duplicate"],
        "vocabulary_size": len(lexicon),
        "total_tokens": total_tokens,
        "avg_doc_length": round(total_tokens / n_docs, 2) if n_docs else 0,
        "median_abstract_words": statistics.median(abstract_word_counts) if abstract_word_counts else 0,
        "forward_entries": forward_entries,
        "inverted_postings": inv["postings"],
        "inverted_words": inv["words"],
        "inverted_runs_merged": inv["runs"],
        "seconds_pass1_lexicon_forward": round(t1 - t0, 2),
        "seconds_pass2_inverted": round(t2 - t1, 2),
        "seconds_total": round(t2 - t0, 2),
        "peak_memory_mb": _peak_memory_mb(),
        "file_sizes_mb": {
            name: round(os.path.getsize(path(name)) / 1e6, 3)
            for name in (config.LEXICON_FILE, config.DOCS_FILE, config.FORWARD_FILE,
                         config.INVERTED_FILE, config.INVERTED_OFFSETS_FILE)
        },
    }
    with open(path(config.STATS_FILE), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build lexicon, forward index and inverted index.")
    ap.add_argument("--input", required=True, help="arXiv metadata JSONL file (or subset)")
    ap.add_argument("--out", default="index_data", help="output directory (default: index_data)")
    ap.add_argument("--limit", type=int, default=None, help="index only the first N valid documents")
    ap.add_argument("--batch-docs", type=int, default=5000,
                    help="documents per in-memory batch when building the inverted index")
    args = ap.parse_args(argv)

    stats = build(args.input, args.out, limit=args.limit, batch_docs=args.batch_docs)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
