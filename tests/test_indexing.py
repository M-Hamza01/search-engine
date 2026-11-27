"""Tests for Stage 2.  Run from the project root:   python -m unittest discover -s tests -v"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from indexer import config
from indexer.build_index import build
from indexer.corpus import DocStoreReader, iter_documents
from indexer.inverted_index import InvertedIndexReader
from indexer.lexicon import Lexicon
from indexer.lookup import intersect_sorted
from indexer.tokenizer import tokenize, tokenize_categories

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "data", "sample_arxiv.jsonl")


def write_jsonl(path, records, raw_lines=()):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
        for line in raw_lines:
            f.write(line + "\n")


class TokenizerTests(unittest.TestCase):
    def test_lowercase_punctuation_and_latex(self):
        self.assertEqual(tokenize("Maurer--Cartan elements in $P_n$-algebras"),
                         ["maurer", "cartan", "elements", "in", "algebras"])

    def test_accent_folding_and_short_tokens(self):
        self.assertEqual(tokenize("Erdős a b cd"), ["erdos", "cd"])

    def test_stop_words_are_kept(self):
        self.assertEqual(tokenize("Data structures and Algorithms"),
                         ["data", "structures", "and", "algorithms"])

    def test_empty(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(None), [])

    def test_categories(self):
        self.assertEqual(tokenize_categories("cs.GT cs.MA"), ["cs.gt", "cs", "cs.ma", "cs"])
        self.assertEqual(tokenize_categories("hep-th"), ["hep-th"])


class LexiconTests(unittest.TestCase):
    def test_ids_unique_dense_and_stable(self):
        lex = Lexicon()
        ids = [lex.get_or_add(w) for w in ["b", "a", "b", "c"]]
        self.assertEqual(ids, [0, 1, 0, 2])
        self.assertEqual(len(lex), 3)
        self.assertIsNone(lex.get("zzz"))
        self.assertEqual(lex.id_to_word[1], "a")

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            lex = Lexicon()
            for w in ["alpha", "beta", "gamma"]:
                lex.get_or_add(w)
            lex.save(os.path.join(d, "lex.json"))
            again = Lexicon.load(os.path.join(d, "lex.json"))
            self.assertEqual(again.word_to_id, lex.word_to_id)
            self.assertEqual(again.id_to_word, lex.id_to_word)


class CorpusTests(unittest.TestCase):
    def test_bad_records_are_skipped_and_counted(self):
        from collections import Counter
        good = {"id": "1", "title": "T", "abstract": "some words", "authors": "A", "categories": "cs.IR",
                "update_date": "2020-01-01"}
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            write_jsonl(p, [good, dict(good), {"id": "", "title": "no id"}, {"id": "9", "title": "", "abstract": ""}],
                        raw_lines=["{not json", "", "[1,2]"])
            stats = Counter()
            docs = list(iter_documents(p, stats=stats))
        self.assertEqual(len(docs), 1)
        self.assertEqual(stats["skipped_duplicate"], 1)
        self.assertEqual(stats["skipped_invalid"], 2)
        self.assertEqual(stats["skipped_malformed"], 2)

    def test_whitespace_collapsed_and_ids_dense(self):
        recs = [{"id": str(i), "title": "A\n  B", "abstract": "x"} for i in range(3)]
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.jsonl")
            write_jsonl(p, recs)
            docs = list(iter_documents(p))
        self.assertEqual([x.doc_id for x in docs], [0, 1, 2])
        self.assertEqual(docs[0].title, "A B")


class HandCheckedIndexTests(unittest.TestCase):
    """A tiny corpus whose index we can verify by hand."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        d = cls._tmp.name
        recs = [
            {"id": "a", "title": "Graph search", "authors": "Ann Lee", "categories": "cs.DS",
             "update_date": "2020-05-01", "abstract": "We search a graph. Search is fast."},
            {"id": "b", "title": "Tree", "authors": "Bob Ray", "categories": "cs.DS cs.IR",
             "update_date": "2021-05-01", "abstract": "A tree is a graph."},
        ]
        write_jsonl(os.path.join(d, "in.jsonl"), recs)
        cls.out = os.path.join(d, "out")
        cls.stats = build(os.path.join(d, "in.jsonl"), cls.out)
        cls.lex = Lexicon.load(os.path.join(cls.out, config.LEXICON_FILE))
        cls.inv = InvertedIndexReader(os.path.join(cls.out, config.INVERTED_FILE),
                                      os.path.join(cls.out, config.INVERTED_OFFSETS_FILE))

    @classmethod
    def tearDownClass(cls):
        cls.inv.close()
        cls._tmp.cleanup()

    def posting(self, word):
        return self.inv.postings(self.lex.get(word))

    def test_term_frequencies_per_field(self):
        # "search": doc0 title 1x, abstract 2x ("We search a graph. Search is fast." -> first at pos 1)
        self.assertEqual(self.posting("search"), [[0, 1, 0, 2, 0, 1]])

    def test_word_in_two_documents(self):
        # one-letter tokens ("a") are dropped BEFORE positions are counted:
        # doc0 abstract tokens: we(0) search(1) graph(2) ...   doc1: tree(0) is(1) graph(2)
        self.assertEqual(self.posting("graph"), [[0, 1, 0, 1, 0, 2], [1, 0, 0, 1, 0, 2]])

    def test_author_and_category_fields(self):
        self.assertEqual(self.posting("ann"), [[0, 0, 1, 0, 0, -1]])
        self.assertEqual([p[0] for p in self.posting("cs")], [0, 1])       # top-level category token
        self.assertEqual(self.posting("cs.ir"), [[1, 0, 0, 0, 1, -1]])

    def test_unknown_word_and_missing_id(self):
        self.assertIsNone(self.lex.get("quantum"))
        self.assertEqual(self.inv.postings(10**6), [])

    def test_stats(self):
        self.assertEqual(self.stats["documents"], 2)
        self.assertEqual(self.stats["vocabulary_size"], len(self.lex))

    def test_and_intersection(self):
        self.assertEqual(intersect_sorted([0, 2, 5, 9], [2, 3, 9, 10]), [2, 9])
        self.assertEqual(intersect_sorted([], [1]), [])


class SampleDataConsistencyTests(unittest.TestCase):
    """Forward and inverted index must describe exactly the same (doc, word) pairs."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = cls._tmp.name
        # tiny batch size forces many runs, so the k-way merge is really exercised
        cls.stats = build(SAMPLE, cls.out, batch_docs=7)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_many_runs_were_merged(self):
        self.assertGreater(self.stats["inverted_runs_merged"], 5)

    def test_inverted_equals_forward(self):
        from_forward = {}
        with open(os.path.join(self.out, config.FORWARD_FILE), encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                for wid, *hits in rec["w"]:
                    from_forward.setdefault(wid, []).append([rec["d"]] + hits)
        from_inverted = {}
        with open(os.path.join(self.out, config.INVERTED_FILE), encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.assertEqual(rec["df"], len(rec["p"]))
                from_inverted[rec["w"]] = rec["p"]
        self.assertEqual(from_forward, from_inverted)

    def test_postings_sorted_and_unique_and_lines_sorted_by_word(self):
        last_wid = -1
        with open(os.path.join(self.out, config.INVERTED_FILE), encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                self.assertGreater(rec["w"], last_wid)
                last_wid = rec["w"]
                ids = [p[0] for p in rec["p"]]
                self.assertEqual(ids, sorted(set(ids)))

    def test_every_lexicon_word_has_postings(self):
        lex = Lexicon.load(os.path.join(self.out, config.LEXICON_FILE))
        with InvertedIndexReader(os.path.join(self.out, config.INVERTED_FILE),
                                 os.path.join(self.out, config.INVERTED_OFFSETS_FILE)) as inv:
            for wid in range(len(lex)):
                self.assertTrue(inv.postings(wid), f"word {lex.id_to_word[wid]!r} has no postings")

    def test_document_store_random_access(self):
        with DocStoreReader(os.path.join(self.out, config.DOCS_FILE),
                            os.path.join(self.out, config.DOCS_OFFSETS_FILE)) as store:
            self.assertEqual(len(store), self.stats["documents"])
            self.assertEqual(store.get(0)["id"], "1608.01482")
            self.assertEqual(store.get(1)["id"], "2106.11502")
            self.assertEqual(store.get(1)["date_ord"] > 0, True)

    def test_real_record_searchable(self):
        lex = Lexicon.load(os.path.join(self.out, config.LEXICON_FILE))
        with InvertedIndexReader(os.path.join(self.out, config.INVERTED_FILE),
                                 os.path.join(self.out, config.INVERTED_OFFSETS_FILE)) as inv:
            self.assertEqual([p[0] for p in inv.postings(lex.get("coisotropic"))], [0])
            self.assertEqual([p[0] for p in inv.postings(lex.get("holliday"))], [1])

    def test_rebuild_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d2:
            build(SAMPLE, d2, batch_docs=1000)
            for name in (config.LEXICON_FILE, config.FORWARD_FILE, config.INVERTED_FILE):
                with open(os.path.join(self.out, name), "rb") as a, open(os.path.join(d2, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), f"{name} differs with a different batch size")


if __name__ == "__main__":
    unittest.main()