"""Threshold and top_k calibration analysis. Reuses the raw (unthresholded,
top-20) candidate lists already captured per case during the single full
evaluation pass (evaluation.runner.run_one_case) -- no extra DB or LLM
calls are needed to simulate a different threshold/top_k, since both are
pure post-hoc filters over the same underlying similarity scores.

Caveat, disclosed in the report: this sweep is only as good as the
embedding provider used for the underlying run. In BLOCKED_BY_CREDENTIALS
mode (FakeEmbeddingProvider's bag-of-words similarity), the sweep shows
the correct SHAPE of the threshold/top_k trade-off (looser threshold ->
higher recall but more irrelevant context; tighter -> the opposite) but
the specific crossover values are not assumed to transfer directly to
Voyage's real cosine-similarity distribution -- re-running this sweep
once live Voyage credentials are available is the recommended next step,
not a rerun of this code (identical harness, different provider).
"""

from dataclasses import dataclass

from evaluation.types import CaseResult

THRESHOLD_CANDIDATES = [0.1, 0.2, 0.3, 0.4, 0.5]
TOP_K_CANDIDATES = [5, 8, 12]


@dataclass
class ConfigOutcome:
    threshold: float
    top_k: int
    recall_at_k: float | None
    false_insufficient_rate: float | None
    correct_insufficient_rate: float | None
    avg_irrelevant_survivor_fraction: float | None
    avg_context_items_sent: float | None


def _survivors(result: CaseResult, *, threshold: float, top_k: int) -> list:
    ranked = sorted(result.retrieved, key=lambda c: c.rank)
    return [c for c in ranked if c.score >= threshold][:top_k]


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def simulate_config(results: list[CaseResult], *, threshold: float, top_k: int) -> ConfigOutcome:
    grounded = [r for r in results if not r.diagnostic_only and r.expected_chunk_ids]
    insufficient_truth = [r for r in results if not r.diagnostic_only and not r.expected_sufficient]

    recall_hits = 0
    false_insufficient = 0
    for r in grounded:
        survivors = _survivors(r, threshold=threshold, top_k=top_k)
        if {c.chunk_id for c in survivors} & set(r.expected_chunk_ids):
            recall_hits += 1
        if not survivors:
            false_insufficient += 1

    correct_insufficient = sum(
        1 for r in insufficient_truth if not _survivors(r, threshold=threshold, top_k=top_k)
    )

    irrelevant_fractions: list[float] = []
    context_sizes: list[int] = []
    for r in results:
        if r.diagnostic_only:
            continue
        survivors = _survivors(r, threshold=threshold, top_k=top_k)
        context_sizes.append(len(survivors))
        if r.expected_document_ids and survivors:
            irrelevant = sum(1 for c in survivors if c.document_id not in set(r.expected_document_ids))
            irrelevant_fractions.append(irrelevant / len(survivors))

    return ConfigOutcome(
        threshold=threshold,
        top_k=top_k,
        recall_at_k=_rate(recall_hits, len(grounded)),
        false_insufficient_rate=_rate(false_insufficient, len(grounded)),
        correct_insufficient_rate=_rate(correct_insufficient, len(insufficient_truth)),
        avg_irrelevant_survivor_fraction=(
            round(sum(irrelevant_fractions) / len(irrelevant_fractions), 4) if irrelevant_fractions else None
        ),
        avg_context_items_sent=(
            round(sum(context_sizes) / len(context_sizes), 2) if context_sizes else None
        ),
    )


def sweep_thresholds(results: list[CaseResult], *, top_k: int) -> list[ConfigOutcome]:
    return [simulate_config(results, threshold=t, top_k=top_k) for t in THRESHOLD_CANDIDATES]


def sweep_top_k(results: list[CaseResult], *, threshold: float) -> list[ConfigOutcome]:
    return [simulate_config(results, threshold=threshold, top_k=k) for k in TOP_K_CANDIDATES]

