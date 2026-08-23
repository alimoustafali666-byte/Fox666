"""Shared result types produced by the runner and consumed by metrics.py
and report.py. Kept separate from both so neither has to import the other.
"""

import uuid
from dataclasses import dataclass, field


@dataclass
class RetrievedChunkDiagnostic:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_key: str | None
    rank: int
    score: float
    above_threshold: bool


@dataclass
class CaseResult:
    case_id: str
    category: str
    question: str
    config_label: str  # e.g. "threshold=0.3,top_k=12"
    diagnostic_only: bool

    # Ground truth (copied from the EvalCase for self-contained reporting)
    expected_sufficient: bool
    expected_answer_contains: list[str]
    expected_answer_not_contains: list[str]
    expected_document_keys: list[str]
    expected_document_ids: list[uuid.UUID] = field(default_factory=list)

    # Retrieval diagnostics -- captured independently of whether Claude
    # was ever called, so a retrieval failure is distinguishable from a
    # generation failure.
    retrieved: list[RetrievedChunkDiagnostic] = field(default_factory=list)
    expected_chunk_ids: list[uuid.UUID] = field(default_factory=list)
    embedding_latency_ms: float = 0.0
    postgres_retrieval_latency_ms: float = 0.0

    @property
    def retrieval_latency_ms(self) -> float:
        return self.embedding_latency_ms + self.postgres_retrieval_latency_ms

    # End-to-end ask() result
    http_status: int = 0
    actual_sufficient: bool | None = None
    actual_answer: str = ""
    actual_citation_document_ids: list[uuid.UUID] = field(default_factory=list)
    actual_citation_chunk_ids: list[uuid.UUID] = field(default_factory=list)
    citation_supports_answer: list[bool] = field(default_factory=list)
    llm_called: bool = False
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None

    # Derived pass/fail (computed by metrics.py, stored back for the report)
    sufficiency_correct: bool | None = None
    answer_exact_match: bool | None = None  # None = not applicable (no expected_answer_contains)
    forbidden_content_leaked: bool = False
    retrieval_recall_at_1: bool | None = None
    retrieval_recall_at_3: bool | None = None
    retrieval_recall_at_5: bool | None = None

