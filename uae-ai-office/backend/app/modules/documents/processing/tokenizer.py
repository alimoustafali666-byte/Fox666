"""Token counting is an abstraction, not a permanent commitment to one
LLM vendor's tokenizer. token_count is informational only at this stage
-- nothing here feeds an embedding or LLM API yet. Swap
ApproximateTokenCounter for a real tokenizer behind the same interface
once a specific embedding/LLM vendor is chosen.
"""

import math
from typing import Protocol


class TokenCounter(Protocol):
    def count(self, text: str) -> int: ...


class ApproximateTokenCounter:
    """~4 characters per token: a commonly cited, deterministic rule of
    thumb for English text across GPT/Claude-family tokenizers. Good
    enough for chunk-sizing decisions; not represented as exact.
    """

    _CHARS_PER_TOKEN = 4

    def count(self, text: str) -> int:
        if not text:
            return 0
        return max(1, math.ceil(len(text) / self._CHARS_PER_TOKEN))


default_token_counter: TokenCounter = ApproximateTokenCounter()

