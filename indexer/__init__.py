"""Indexing package for the CS-250 DSA search-engine project (Stage 2).

Modules
-------
config         shared constants (file names, posting layout)
tokenizer      text -> list of normalised tokens
corpus         reads the arXiv JSONL file, cleans records, stores document metadata
lexicon        word <-> unique integer id
forward_index  document -> words (with per-field counts and position)
inverted_index word -> documents (built from the forward index, memory-bounded)
build_index    command line entry point that runs the whole pipeline
lookup         small command line tool to inspect the generated index files
"""
