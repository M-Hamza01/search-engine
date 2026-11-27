"""Extract an evenly spread subset from the full arXiv metadata dump.

The Kaggle file has ~2.5 million records.  Taking just the first N would give only old
papers, so this picks exactly N qualifying records spread evenly across the file.

    python tools/make_subset.py --input arxiv-metadata-oversnapshot.json \
           --output arxiv_subset_75k.jsonl --count 75000

Two passes: the first counts the qualifying records, the second writes every k-th one.
A record qualifies if it is valid JSON, has an id and a title, and its abstract has at
least ``--min-words`` words (filters out "Withdrawn" / empty abstracts).
"""

import argparse
import json


def qualifies(line: str, min_words: int):
    try:
        rec = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(rec, dict) or not rec.get("id") or not (rec.get("title") or "").strip():
        return None
    if len((rec.get("abstract") or "").split()) < min_words:
        return None
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--count", type=int, default=75000)
    ap.add_argument("--min-words", type=int, default=30)
    args = ap.parse_args()

    # pass 1: how many records qualify?
    total = 0
    with open(args.input, "r", encoding="utf-8") as f:
        for line in f:
            if qualifies(line, args.min_words):
                total += 1
    count = min(args.count, total)
    print(f"{total} qualifying records, selecting {count}")

    # pass 2: write record i when floor((i+1)*count/total) increases -> exactly `count`, evenly spaced
    written = seen = 0
    with open(args.input, "r", encoding="utf-8") as f, \
            open(args.output, "w", encoding="utf-8", newline="\n") as out:
        for line in f:
            if not qualifies(line, args.min_words):
                continue
            seen += 1
            if (seen * count) // total > ((seen - 1) * count) // total:
                out.write(line if line.endswith("\n") else line + "\n")
                written += 1
    print(f"wrote {written} records to {args.output}")


if __name__ == "__main__":
    main()
