# CS-250 DSA Project – Stage 2: Lexicon, Forward Index, Inverted Index

Team SE16-B: Muhammad Hamza (553436), Muhammad Rayyan Bilal (545830), Muhammad Asfand Khan (554959)
Dataset: Cornell University arXiv metadata (CC0 1.0), 75,000-paper subset. Python 3.9+, **standard library only**.

## Run it

```bash
# 0. (once) cut the 75k subset out of the Kaggle file – evenly spread over all years
python tools/make_subset.py --input arxiv-metadata-oversnapshot.json --output data/arxiv_subset_75k.jsonl --count 75000

# 1. build lexicon + forward index + inverted index
python -m indexer.build_index --input data/arxiv_subset_75k.jsonl --out index_data

# quick demo on the bundled test data (402 records, <1 second)
python -m indexer.build_index --input data/sample_arxiv.jsonl --out index_data

# 2. inspect the result
python -m indexer.lookup --index-dir index_data --word coisotropic
python -m indexer.lookup --index-dir index_data --and voting election preference

# 3. tests
python -m unittest discover -s tests -v
```

## What is produced (`index_data/`, no database – plain files)

| File | Contents |
|---|---|
| `lexicon.json` | `{"word": word_id}`; ids are dense 0..N-1 in order of first appearance |
| `forward_index.jsonl` | one line per doc: `{"d": doc_id, "n": length, "w": [[word_id, tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_pos], ...]}` |
| `inverted_index.jsonl` | one line per word, sorted by word id: `{"w": word_id, "df": n, "p": [[doc_id, tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_pos], ...]}`, postings sorted by doc id |
| `inverted.offsets.bin` | uint64 byte offset of each word's line → one seek reads one word's postings (the hook for barrels in Stage 3) |
| `docs.jsonl` + `docs.offsets.bin` | document table (title, authors, categories, date, abstract) with random access by doc id |
| `build_stats.json` | counts, timings, peak memory, median abstract length |

The per-field counts and `first_abstract_pos` are stored now because Stage 4 ranking needs them
(title/author hits weigh more than abstract hits; earlier mention is better; `date_ord` in `docs.jsonl` gives the recency boost).

## Design and why (viva notes)

* **Tokenizer** (`tokenizer.py`): lower-case, accent folding, tokens = runs of `[a-z0-9]`, drop 1-char and >40-char tokens.
  Stop words are *kept* because the spec requires "Data structures **and** Algorithms" to match all four words.
  No stemming, so lexicon words also exist in the pre-trained embeddings used for semantic search later.
  The same function must be used for queries.
* **Lexicon**: hash map `word → id` plus array `id → word`, both O(1). New words (dynamic addition) get the next id; old ids never change.
* **Forward index**: built in the same pass as the lexicon (`analyze_document`), streamed to disk one document at a time.
  `analyze_document` is reused later for documents uploaded at runtime.
* **Inverted index**: built from the forward index by an **external sort-merge (SPIMI)**:
  1. invert batches of 5,000 documents in RAM and write each as a sorted "run";
  2. k-way merge the runs with `heapq.merge` (a min-heap). Docs are read in id order, and the merge is stable, so each word's postings stay sorted by doc id.

  RAM depends on the batch size, not on corpus size. Complexity: O(P log R) for P postings and R runs.
* **Offsets file**: word id → byte offset gives O(1) random access to a posting list – no scanning, no loading the whole index.
* **No database**: only files, as the spec demands. Files with offsets are written in binary so offsets are exact on Windows too.
* **Robustness**: malformed JSON lines, records with no id/text and duplicate ids are skipped and counted in `build_stats.json`.

## Measured results

| Corpus | Docs | Vocabulary | Postings | Build time | Peak RAM |
|---|---|---|---|---|---|
| `data/sample_arxiv.jsonl` (2 real + 400 synthetic) | 402 | 305 | 21,858 | 0.15 s | 20 MB |
| `data/arxiv_subset_75k.jsonl` (real arXiv subset) | 75,000 | 228,294 | 8,266,452 | 67.62 s | Not available on Windows |
| Stress test: synthetic Zipf corpus, 120k-word vocabulary, ~150 words/doc | 75,000 | 120,006 | 9,752,854 | 58 s | 122 MB |

The stress test used generated text, not real arXiv data (the real file was not reachable from where this was built), so
**rerun the build on your real 75k subset and put its numbers in your documentation.**

## Test data

`data/sample_arxiv.jsonl` = the two real records from the Kaggle file + 400 synthetic records (ids start with `synthetic-`,
made by `tools/make_sample_data.py`). For a real-data test file, use the first lines of the Kaggle dump:
`head -n 1000 arxiv-metadata-oversnapshot.json > data/real_arxiv_1000.jsonl`.

## Layout

```
indexer/      tokenizer, corpus, lexicon, forward_index, inverted_index, build_index (CLI), lookup (CLI), config
tools/        make_subset.py, make_sample_data.py
tests/        test_indexing.py  (22 tests, incl. forward == inverted consistency and k-way merge)
data/         sample_arxiv.jsonl
```

## Next stages

* **Barrels (Stage 3)**: split `inverted_index.jsonl` by word-id range (balanced by posting count) and load only the barrels of the query words.
* **Search / ranking / autocomplete / semantic search**: use `Lexicon` (trie for autocomplete), `InvertedIndexReader`, `DocStoreReader`.
* Query categories as `cs.gt` need the dot kept – use `tokenize_categories` for such terms.
