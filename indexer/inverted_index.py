"""Inverted index: for each word, the documents that contain it.

One line per word in ``inverted_index.jsonl``, sorted by word id::

    {"w": 42, "df": 3, "p": [[doc_id, tf_title, tf_authors, tf_abstract, tf_cats, first_abs_pos], ...]}

postings ``p`` are sorted by doc_id.  ``inverted.offsets.bin`` holds, for every word
id, the byte offset of its line, so one word's postings can be read with a single
seek - this is what lets the search stage (and the barrels of Stage 3) avoid loading
the whole index into RAM.

How it is built without holding everything in RAM  (external sort-merge / "SPIMI")
1. Read the forward index in batches of ``batch_docs`` documents.  For each batch
   invert it in memory (word -> postings) and write that "run" to a temp file,
   sorted by word id.
2. K-way merge all runs with a heap.  Documents are processed in ascending id order,
   so for one word the postings of run 0 all have smaller doc ids than those of
   run 1, etc.; concatenating them in run order keeps each list sorted.
Memory is bounded by the batch size, not by the corpus size.
"""

import heapq
import json
import os
import tempfile
from array import array
from typing import Iterator, List, Optional, Tuple

from .config import MISSING_OFFSET
from .forward_index import iter_forward_index


# ------------------------------------------------------------------- build
def _write_run(batch: dict, run_dir: str, run_no: int) -> str:
    """Write one in-memory partial inverted index, sorted by word id."""
    path = os.path.join(run_dir, f"run_{run_no:05d}.jsonl")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for wid in sorted(batch):
            f.write(json.dumps({"w": wid, "p": batch[wid]}, separators=(",", ":")) + "\n")
    return path


def _iter_run(path: str) -> Iterator[Tuple[int, list]]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            yield rec["w"], rec["p"]


def build_inverted_index(forward_path: str, inverted_path: str, offsets_path: str,
                         vocab_size: int, batch_docs: int = 5000,
                         tmp_dir: Optional[str] = None) -> dict:
    """Build ``inverted_index.jsonl`` + offsets from a forward index.

    Returns a dict with ``words`` (distinct words with postings), ``postings`` and ``runs``.
    """
    with tempfile.TemporaryDirectory(dir=tmp_dir, prefix="inv_runs_") as run_dir:
        # ---- phase 1: produce sorted runs --------------------------------
        run_paths = []
        batch = {}
        docs_in_batch = 0
        for doc_id, _n, entries in iter_forward_index(forward_path):
            for wid, t, a, ab, c, pos in entries:
                batch.setdefault(wid, []).append([doc_id, t, a, ab, c, pos])
            docs_in_batch += 1
            if docs_in_batch >= batch_docs:
                run_paths.append(_write_run(batch, run_dir, len(run_paths)))
                batch, docs_in_batch = {}, 0
        if batch:
            run_paths.append(_write_run(batch, run_dir, len(run_paths)))

        # ---- phase 2: k-way merge of the runs -----------------------------
        offsets = array("Q", [MISSING_OFFSET]) * vocab_size
        words = postings_total = 0
        merged = heapq.merge(*(_iter_run(p) for p in run_paths), key=lambda item: item[0])

        with open(inverted_path, "wb") as out:      # binary so offsets are exact
            position = 0

            def emit(wid: int, plist: List[list]) -> None:
                nonlocal position, words, postings_total
                line = json.dumps({"w": wid, "df": len(plist), "p": plist},
                                  separators=(",", ":")) + "\n"
                data = line.encode("utf-8")
                offsets[wid] = position
                out.write(data)
                position += len(data)
                words += 1
                postings_total += len(plist)

            current, acc = None, []
            for wid, plist in merged:
                if wid != current:
                    if current is not None:
                        emit(current, acc)
                    current, acc = wid, []
                acc.extend(plist)       # heapq.merge is stable -> doc ids stay ascending
            if current is not None:
                emit(current, acc)

        with open(offsets_path, "wb") as f:
            offsets.tofile(f)

    return {"words": words, "postings": postings_total, "runs": len(run_paths)}


# ------------------------------------------------------------------ reading
class InvertedIndexReader:
    """Random access to the postings of one word id (one seek + one readline)."""

    def __init__(self, inverted_path: str, offsets_path: str):
        self._offsets = array("Q")
        with open(offsets_path, "rb") as f:
            self._offsets.frombytes(f.read())
        self._f = open(inverted_path, "rb")

    def postings(self, word_id: int) -> List[list]:
        """Postings of ``word_id`` sorted by doc id, or [] if it has none."""
        if not 0 <= word_id < len(self._offsets):
            return []
        offset = self._offsets[word_id]
        if offset == MISSING_OFFSET:
            return []
        self._f.seek(offset)
        return json.loads(self._f.readline().decode("utf-8"))["p"]

    def doc_freq(self, word_id: int) -> int:
        return len(self.postings(word_id))

    def close(self) -> None:
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()