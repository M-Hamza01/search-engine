"""Lexicon: the list of all distinct words, each with a unique integer id.

The id is the identifier used by the forward and inverted indices instead of the
word string (smaller files, faster comparisons, and ids can be range-partitioned
into barrels in Stage 3).

Ids are dense integers 0..N-1 assigned in order of first appearance, so
``id_to_word[id]`` is a plain list lookup and a new word added later (dynamic
content addition) simply receives the next free id without disturbing old ones.
"""

import json
import os
from typing import Optional


class Lexicon:
    def __init__(self):
        self.word_to_id = {}   # hash map: word -> id   (O(1) lookup)
        self.id_to_word = []   # array:    id -> word   (O(1) lookup)

    def __len__(self) -> int:
        return len(self.id_to_word)

    def __contains__(self, word: str) -> bool:
        return word in self.word_to_id

    def get(self, word: str) -> Optional[int]:
        """Id of ``word`` or None if the word is unknown (used at query time)."""
        return self.word_to_id.get(word)

    def get_or_add(self, word: str) -> int:
        """Id of ``word``; creates a new entry if this is the first time we see it."""
        wid = self.word_to_id.get(word)
        if wid is None:
            wid = len(self.id_to_word)
            self.word_to_id[word] = wid
            self.id_to_word.append(word)
        return wid

    # ------------------------------------------------------------ persistence
    def save(self, path: str) -> None:
        """Write ``{"word": id}`` as JSON.  Written to a temp file first and then
        renamed, so a crash can never leave a half-written lexicon behind."""
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.word_to_id, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str) -> "Lexicon":
        with open(path, "r", encoding="utf-8") as f:
            word_to_id = json.load(f)
        lex = cls()
        lex.id_to_word = [None] * len(word_to_id)
        for word, wid in word_to_id.items():
            lex.id_to_word[wid] = word
        if any(w is None for w in lex.id_to_word):
            raise ValueError(f"{path}: word ids are not dense 0..N-1 (corrupt lexicon)")
        lex.word_to_id = word_to_id
        return lex
