"""Deterministic, network-free LLM provider for the test suite (and
available as a local-dev fallback, LLM_PROVIDER=fake -- never production,
since it performs no real reasoning). Mirrors
app.core.embeddings.fake_provider's role and rationale.

Two modes, chosen per-test:

- **Scripted** (`enqueue`/`enqueue_error`): the test pushes exact
  GroundedAnswerResult/exception values it wants returned, in order --
  used by tests that need full control (structured-output validation,
  citation-fabrication rejection, retry behavior, provider-failure
  handling).
- **Default grounding** (nothing enqueued): returns a small, honest,
  rule-based "grounded answer" computed only from
  request.document_context -- picks the context item whose content most
  overlaps the question's words and cites it, or reports insufficient
  information if none overlap at all. This is what the adversarial
  prompt-injection integration test and the plain end-to-end ask tests
  use: it proves the *pipeline* (retrieval -> context assembly ->
  citation validation -> persistence) handles a well-behaved model
  correctly, and that injected instruction text embedded in
  document_context is never treated as anything but inert data by this
  provider (it is only ever scanned for word-overlap, like any other
  content). It is NOT a claim about what the real Claude API would do --
  see the Step 11 report's disclosure that live prompt-injection
  resistance is unverified in this environment (no network/API key),
  exactly like Voyage AI in Step 10.
"""

import re

from app.core.llm.provider import (
    BriefGeneratedItem,
    BriefGenerationRequest,
    BriefGenerationResult,
    CollaborationInsightsRequest,
    CollaborationInsightsResult,
    GroundedAnswerCitation,
    GroundedAnswerRequest,
    GroundedAnswerResult,
    LLMProvider,
)

# Unicode-aware (not [a-z0-9]+): see app.core.embeddings.fake_provider's
# module docstring for why -- the ASCII-only version made this provider's
# word-overlap grounding blind to Arabic (and any non-Latin-script) text,
# always falling through to "insufficient information" regardless of
# actual overlap.
_WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


class FakeLLMProvider(LLMProvider):
    def __init__(self, *, model: str = "fake-llm-v1") -> None:
        self._model = model
        self._queue: list[GroundedAnswerResult | Exception] = []
        self.calls: list[GroundedAnswerRequest] = []
        self._brief_queue: list[BriefGenerationResult | Exception] = []
        self.brief_calls: list[BriefGenerationRequest] = []
        self._insights_queue: list[CollaborationInsightsResult | Exception] = []
        self.insights_calls: list[CollaborationInsightsRequest] = []

    @property
    def model_identifier(self) -> str:
        return self._model

    def enqueue(self, result: GroundedAnswerResult) -> None:
        self._queue.append(result)

    def enqueue_error(self, exc: Exception) -> None:
        self._queue.append(exc)

    def generate_grounded_answer(self, request: GroundedAnswerRequest) -> GroundedAnswerResult:
        self.calls.append(request)

        if self._queue:
            item = self._queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        return self._default_grounded_answer(request)

    def _default_grounded_answer(self, request: GroundedAnswerRequest) -> GroundedAnswerResult:
        question_words = _words(request.question)
        best_ref: str | None = None
        best_overlap = 0
        for item in request.document_context:
            overlap = len(question_words & _words(item.content))
            if overlap > best_overlap:
                best_overlap = overlap
                best_ref = item.ref

        if best_ref is None:
            return GroundedAnswerResult(
                answer="I don't have enough information in the available documents.",
                sufficient=False,
                citations=[],
                model_identifier=self._model,
                input_tokens=len(question_words) + sum(len(_words(i.content)) for i in request.document_context),
                output_tokens=12,
            )

        cited_content = next(i.content for i in request.document_context if i.ref == best_ref)
        return GroundedAnswerResult(
            answer=cited_content.strip(),
            sufficient=True,
            citations=[GroundedAnswerCitation(ref=best_ref)],
            model_identifier=self._model,
            input_tokens=len(question_words) + sum(len(_words(i.content)) for i in request.document_context),
            output_tokens=len(_words(cited_content)),
        )

    def enqueue_brief(self, result: BriefGenerationResult) -> None:
        self._brief_queue.append(result)

    def enqueue_brief_error(self, exc: Exception) -> None:
        self._brief_queue.append(exc)

    def generate_daily_brief(self, request: BriefGenerationRequest) -> BriefGenerationResult:
        self.brief_calls.append(request)

        if self._brief_queue:
            item = self._brief_queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        return self._default_brief(request)

    def _default_brief(self, request: BriefGenerationRequest) -> BriefGenerationResult:
        """One "new_information" item per new document (proves the
        pipeline delivers bounded, real document content through to the
        model), plus every carry-forward item echoed back unchanged
        (proves carry-forward plumbing works) -- no real judgment about
        what's resolved vs. still open, since this provider does no real
        reasoning. Never called by brief_orchestrator when there's
        nothing new AND nothing carried forward (that's the fixed-
        template, no-LLM-call path) -- so this only needs to handle the
        case where there's something to summarize.
        """
        items = [
            BriefGeneratedItem(
                category="new_information",
                text=doc.content.strip()[:200],
                priority=2,
                source_ref=doc.ref,
            )
            for doc in request.new_documents
        ]
        items.extend(
            BriefGeneratedItem(
                category=carry.category, text=carry.text, priority=carry.priority,
                source_ref=carry.source_ref,
            )
            for carry in request.carry_forward_items
        )

        summary = (
            f"{len(request.new_documents)} new document(s), "
            f"{len(request.carry_forward_items)} carried-forward item(s)."
        )
        total_words = sum(len(_words(d.content)) for d in request.new_documents)
        total_words += sum(len(_words(c.text)) for c in request.carry_forward_items)

        return BriefGenerationResult(
            summary=summary,
            items=items,
            model_identifier=self._model,
            input_tokens=total_words,
            output_tokens=sum(len(_words(i.text)) for i in items) + len(_words(summary)),
        )

    def enqueue_insights(self, result: CollaborationInsightsResult) -> None:
        self._insights_queue.append(result)

    def enqueue_insights_error(self, exc: Exception) -> None:
        self._insights_queue.append(exc)

    def generate_collaboration_insights(
        self, request: CollaborationInsightsRequest
    ) -> CollaborationInsightsResult:
        self.insights_calls.append(request)

        if self._insights_queue:
            item = self._insights_queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        return self._default_insights(request)

    def _default_insights(self, request: CollaborationInsightsRequest) -> CollaborationInsightsResult:
        """Deliberately does no real reasoning: a deterministic summary
        built by concatenating/truncating message content (proves the
        pipeline delivers the real, bounded, already-authorized message
        window through to the model) and EMPTY decisions/action_items --
        never invented pseudo-heuristics (e.g. keyword-matching "decided"/
        "assigned") that could misrepresent what this fake provider is
        actually capable of. Tests that need to exercise decision/action-
        item extraction use enqueue_insights() with a scripted result.
        """
        joined = " ".join(f"[{m.sender_label}] {m.content.strip()}" for m in request.messages)
        summary = joined[:280] if joined else "No messages to summarize."
        total_words = sum(len(_words(m.content)) for m in request.messages)
        return CollaborationInsightsResult(
            summary=summary,
            decisions=[],
            action_items=[],
            model_identifier=self._model,
            input_tokens=total_words,
            output_tokens=len(_words(summary)),
        )

