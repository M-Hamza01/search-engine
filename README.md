# Search Engine — Stage 2 Indexing System

This repository contains the Stage 2 implementation of the CS-250 Data Structures and Algorithms project. It transforms arXiv metadata into the three core structures required by the search engine:

- a lexicon that assigns a stable integer ID to every term;
- a forward index that records the terms present in each document; and
- an inverted index that provides efficient term-to-document lookup.

The implementation uses Python's standard library only. Indexes are stored as plain JSONL and binary-offset files; no database or external indexing framework is used.

## Team

| Member | Student ID | Primary responsibility |
|---|---:|---|
| Muhammad Hamza | 553436 | Build pipeline, configuration, dataset preparation, and documentation |
| Muhammad Rayyan Bilal | 545830 | Tokenization, corpus processing, lexicon, and forward index |
| Muhammad Asfand Khan | 554959 | Inverted index, lookup utilities, and validation tests |

Section: SE16-B

Course: CS-250 Data Structures and Algorithms

## Stage 2 deliverables

The project currently provides:

- deterministic tokenization and normalization;
- dense, stable word IDs in order of first occurrence;
- per-field term frequencies for title, authors, abstract, and categories;
- the first position of each term in the abstract;
- streamed forward-index construction;
- memory-bounded inverted-index construction using external sort-merge;
- random access to documents and posting lists through binary offset tables;
- handling and reporting of malformed, invalid, and duplicate records;
- command-line utilities for building and inspecting an index; and
- 22 automated tests covering individual components and end-to-end consistency.

## Repository structure

```text
data/
  sample_arxiv.jsonl       Reproducible 402-document test corpus
indexer/
  build_index.py           Index construction command-line entry point
  config.py                File names and indexing defaults
  corpus.py                Corpus validation and random-access document store
  forward_index.py         Document analysis and forward-index writer
  inverted_index.py        External sort-merge and posting-list reader
  lexicon.py               Term-to-ID and ID-to-term mappings
  lookup.py                Index inspection command-line utility
  tokenizer.py             Text and category tokenization
tests/
  test_indexing.py         Unit and integration tests
tools/
  make_sample_data.py      Deterministic sample-corpus generator
  make_subset.py           Evenly sampled 75,000-document corpus generator
```

## Requirements

- Python 3.9 or later
- No third-party Python packages

Commands below should be run from the repository root. On systems where `python` is not the Python 3 command, use `python3` or the appropriate Python launcher.

## Quick reproducible demonstration

The repository includes `data/sample_arxiv.jsonl`, containing two real arXiv records and 400 deterministically generated records. It allows the complete pipeline and test suite to run without downloading the full dataset.

Build a sample index:

```bash
python -m indexer.build_index --input data/sample_arxiv.jsonl --out index_data_sample
```

Inspect a posting list and perform an AND query:

```bash
python -m indexer.lookup --index-dir index_data_sample --word coisotropic
python -m indexer.lookup --index-dir index_data_sample --and voting election preference
```

Run the complete automated test suite:

```bash
python -m unittest discover -s tests -v
```

Expected result:

```text
Ran 22 tests
OK
```

## Full 75,000-document build

The evaluation corpus is derived from the [Cornell University arXiv metadata dataset](https://www.kaggle.com/datasets/Cornell-University/arxiv), distributed under CC0 1.0. The original dataset and generated 75,000-record subset are excluded from Git because of their size.

After downloading `arxiv-metadata-oai-snapshot.json`, create a subset evenly distributed across the source file:

```bash
python tools/make_subset.py --input arxiv-metadata-oai-snapshot.json --output data/arxiv_subset_75k.jsonl --count 75000
```

Build the complete Stage 2 index:

```bash
python -m indexer.build_index --input data/arxiv_subset_75k.jsonl --out index_data
```

The `--limit` option can restrict a build to the first N valid documents, while `--batch-docs` controls the number of documents inverted in each in-memory batch.

## Index representation

The build produces the following files:

| File | Purpose |
|---|---|
| `lexicon.json` | Maps each normalized term to a dense word ID |
| `forward_index.jsonl` | Stores the word IDs and field statistics for every document |
| `inverted_index.jsonl` | Stores a sorted posting list for every word ID |
| `inverted.offsets.bin` | Stores a 64-bit byte offset for each posting list |
| `docs.jsonl` | Stores searchable document metadata and text |
| `docs.offsets.bin` | Stores a 64-bit byte offset for each document |
| `build_stats.json` | Records corpus counts, skipped records, timings, and output sizes |

Each forward-index entry has the form:

```text
[word_id, tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_position]
```

Each inverted posting adds the document ID at the beginning:

```text
[doc_id, tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_position]
```

These statistics support later ranking requirements, including field weighting, early-term-position weighting, and recency scoring.

## Algorithms and data structures

### Tokenization

General text is converted to lowercase, Unicode accents are folded, and tokens are extracted as runs of ASCII letters and digits. One-character tokens and tokens longer than 40 characters are discarded. Stop words are retained because queries may require exact conjunctions containing words such as “and.” Categories use a separate tokenizer so identifiers such as `cs.GT` remain searchable as `cs.gt`.

### Lexicon

The lexicon maintains both a hash map from term to word ID and an array from word ID to term. Average lookup and insertion are O(1). IDs are dense and stable: adding a new term never changes an existing term's ID.

### Forward index

Documents are analyzed one at a time. Their forward-index entries and document records are written directly to disk, avoiding the need to retain the complete corpus in memory.

### Inverted index

The inverted index is constructed with a memory-bounded external sort-merge process:

1. Forward-index entries are inverted in configurable document batches.
2. Each batch is written as a run sorted by word ID.
3. Runs are combined with a heap-based k-way merge.
4. Posting lists remain sorted by document ID.

For P postings and R sorted runs, the merge requires O(P log R) time. Memory usage depends primarily on the selected batch size rather than the total corpus size.

### Random access

Binary offset tables map a word ID or document ID to its byte position in the corresponding JSONL file. This allows one seek and one line read instead of scanning or loading the entire index.

## Validation

The test suite verifies:

- token normalization, category handling, and stop-word retention;
- lexicon ID uniqueness, density, stability, and serialization;
- malformed, invalid, and duplicate-record handling;
- per-field term frequencies and abstract positions;
- AND intersection behavior;
- document-store and posting-list random access;
- sorted, unique postings and sorted word IDs;
- equality of all `(document, word)` relationships in the forward and inverted indexes;
- deterministic output across different batch sizes; and
- forced multi-run k-way merging.

## Measured results

The following results were obtained from the included sample and the real 75,000-document subset:

| Corpus | Documents | Vocabulary | Forward/inverted pairs | Total build time |
|---|---:|---:|---:|---:|
| Bundled sample | 402 | 305 | 21,858 | ~0.3 s |
| Real arXiv subset | 75,000 | 228,294 | 8,266,452 | 67.62 s |

For the full build, all 75,000 records were accepted: zero malformed, invalid, or duplicate records were reported. The forward and inverted pair counts were identical, providing an additional consistency check.

Generated indexes and the large source datasets are intentionally ignored by Git. They can be reproduced using the commands above.

## Preparation for later stages

The Stage 2 representation is designed to support the remaining search-engine stages:

- posting lists can be divided into barrels by word-ID range;
- field frequencies and first positions are already available for ranking;
- document dates are stored in ordinal form for recency scoring;
- `Lexicon`, `InvertedIndexReader`, and `DocStoreReader` provide reusable lookup interfaces; and
- category tokens retain the notation required for category-aware queries.
