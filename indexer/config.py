"""Shared constants.  Everything that more than one module must agree on lives here."""

# ---------------------------------------------------------------- output files
LEXICON_FILE = "lexicon.json"                 # {"word": word_id, ...}
DOCS_FILE = "docs.jsonl"                      # one JSON document record per line
DOCS_OFFSETS_FILE = "docs.offsets.bin"        # uint64 byte offset of each docs.jsonl line
FORWARD_FILE = "forward_index.jsonl"          # one line per document
INVERTED_FILE = "inverted_index.jsonl"        # one line per word, sorted by word_id
INVERTED_OFFSETS_FILE = "inverted.offsets.bin"  # uint64 byte offset of each inverted line
STATS_FILE = "build_stats.json"

# ------------------------------------------------------------- field numbering
# Each (document, word) pair stores one term-frequency counter per field so the
# ranking stage can weight a title hit higher than an abstract hit.
FIELDS = ("title", "authors", "abstract", "categories")
TITLE, AUTHORS, ABSTRACT, CATEGORIES = range(4)

# ------------------------------------------------------------------ entry layout
# Forward index entry : [word_id, tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_pos]
# Inverted posting    : [doc_id,  tf_title, tf_authors, tf_abstract, tf_categories, first_abstract_pos]
# first_abstract_pos is the 0-based token position of the first occurrence of the
# word inside the abstract, or -1 if the word does not occur in the abstract.
NO_POSITION = -1

# Marker in the offsets file for "this word id has no postings".
MISSING_OFFSET = 2**64 - 1
