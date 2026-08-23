"""Deterministic, dependency-free embedding provider for the test suite
(and available as a local-dev fallback, EMBEDDING_PROVIDER=fake -- never
production, since it carries no real semantic understanding).

Produces an L2-normalized bag-of-words vector: each lowercased word in
the text is hashed into one of `dimension` buckets, which is
incremented. Two texts sharing more distinctive words end up with
higher cosine similarity, which is enough to let tests assert real
ranking behavior ("a query about X ranks the chunk containing X above
one that doesn't") deterministically, without any real ML model or
network access. This is a testing tool, not a quality embedding model.

Word pattern is Unicode-aware (`[^\\W_]+`, not `[a-z0-9]+`): the ASCII-
only version treated any Arabic-only (or other non-Latin-script) text as
containing zero words, so every such text collapsed to the same
fallback unit vector and became indistinguishable from any other --
silently breaking retrieval-ranking tests for Arabic/multilingual
content (found while building the Step 14 Arabic RAG pipeline-validation
suite). This still has no cross-lingual/semantic understanding at all
-- it only detects literal shared tokens -- which is exactly the
"deterministic pipeline validation, not real quality" role this
provider has always played, just no longer accidentally blind to
non-Latin scripts.
"""

import hashlib
import math
import re

from app.core.embeddings.provider import EmbeddingProvider

_WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def _vector_for(text: str, *, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    for word in _WORD_PATTERN.findall(text.lower()):
        bucket = int(hashlib.sha256(word.encode()).hexdigest(), 16) % dimension
        vector[bucket] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        # No recognizable words (e.g. pure punctuation/numbers) -- a
        # fixed, non-zero unit vector so cosine distance stays
        # well-defined rather than dividing by zero downstream.
        vector[0] = 1.0
        return vector
    return [component / norm for component in vector]


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(self, *, dimension: int, model: str = "fake-embedding-v1") -> None:
        self._dimension = dimension
        self._model = model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_identifier(self) -> str:
        return self._model

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [_vector_for(text, dimension=self._dimension) for text in texts]

    def embed_text(self, text: str) -> list[float]:
        return _vector_for(text, dimension=self._dimension)

    def embed_query(self, text: str) -> list[float]:
        return _vector_for(text, dimension=self._dimension)

