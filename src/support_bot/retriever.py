"""BM25 retrieval over corpus chunks."""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from support_bot.corpus import Chunk

STOP_WORDS = frozenset("the a an of to in is my i do how can and or for on it after".split())


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOP_WORDS]


class Retriever:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self._bm25 = BM25Okapi([tokenize(c.text) for c in chunks])

    def retrieve(self, question: str, k: int = 3) -> list[Chunk]:
        scores = self._bm25.get_scores(tokenize(question))
        ranked = sorted(zip(scores, self.chunks, strict=True), key=lambda pair: pair[0], reverse=True)
        return [chunk for score, chunk in ranked if score > 0][:k]
