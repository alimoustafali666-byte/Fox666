from app.core.llm.fake_provider import FakeLLMProvider
from app.core.llm.provider import (
    DocumentContextItem,
    GroundedAnswerCitation,
    GroundedAnswerRequest,
    GroundedAnswerResult,
)


def test_default_grounding_picks_best_overlapping_chunk_and_cites_it() -> None:
    provider = FakeLLMProvider()
    request = GroundedAnswerRequest(
        question="What are the payment terms?",
        document_context=[
            DocumentContextItem(ref="1", content="Unrelated xylophone marmalade text."),
            DocumentContextItem(ref="2", content="Payment terms are 30 days net from invoice."),
        ],
    )

    result = provider.generate_grounded_answer(request)

    assert result.sufficient is True
    assert result.citations == [GroundedAnswerCitation(ref="2")]
    assert "30 days" in result.answer


def test_default_grounding_reports_insufficient_when_nothing_overlaps() -> None:
    provider = FakeLLMProvider()
    request = GroundedAnswerRequest(
        question="What is the revenue forecast?",
        document_context=[DocumentContextItem(ref="1", content="Zebra umbrella jigsaw kayak.")],
    )

    result = provider.generate_grounded_answer(request)

    assert result.sufficient is False
    assert result.citations == []


def test_enqueued_result_is_returned_in_order() -> None:
    provider = FakeLLMProvider()
    first = GroundedAnswerResult(
        answer="first", sufficient=True, citations=[], model_identifier="fake-llm-v1",
        input_tokens=1, output_tokens=1,
    )
    second = GroundedAnswerResult(
        answer="second", sufficient=True, citations=[], model_identifier="fake-llm-v1",
        input_tokens=1, output_tokens=1,
    )
    provider.enqueue(first)
    provider.enqueue(second)

    request = GroundedAnswerRequest(question="q", document_context=[])
    assert provider.generate_grounded_answer(request).answer == "first"
    assert provider.generate_grounded_answer(request).answer == "second"


def test_enqueued_error_is_raised() -> None:
    provider = FakeLLMProvider()
    provider.enqueue_error(ValueError("boom"))

    request = GroundedAnswerRequest(question="q", document_context=[])
    try:
        provider.generate_grounded_answer(request)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "boom"


def test_calls_are_recorded() -> None:
    provider = FakeLLMProvider()
    request = GroundedAnswerRequest(question="q", document_context=[])
    provider.generate_grounded_answer(request)
    assert provider.calls == [request]

