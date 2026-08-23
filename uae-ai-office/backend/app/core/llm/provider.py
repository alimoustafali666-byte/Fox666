"""The abstraction every module needing a grounded-Q&A LLM call depends
on. Business/domain code (app.modules.conversations' ask_service) must
never import the Anthropic SDK or call a vendor API directly -- only this
interface and the factory that resolves it from configuration
(app.core.llm.factory.get_llm_provider).

CRITICAL ARCHITECTURAL RULE (Step 11): this provider is never the
retrieval engine. Callers select which document_chunks are relevant
(app.modules.documents.retrieval_service) and pass only that already-
selected content in as `document_context`; the provider itself never
searches, never sees anything beyond what it's handed, and never decides
what's relevant.

DOCUMENT CONTENT IS DATA, NOT INSTRUCTIONS. Every DocumentContextItem.content
below is untrusted content extracted from a company's own documents. It is
passed to the provider for grounding only -- never interpreted by this
layer, and required (see anthropic_provider.py's system prompt) to never
be interpreted as an instruction by the model either.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class DocumentContextItem:
    """One retrieved chunk, already selected by the retrieval layer.
    `ref` is a small, provider-neutral alias (e.g. "1", "2") assigned by
    the caller -- the model is never shown the real chunk_id UUID; the
    caller (app.modules.conversations.ask_service) keeps the ref -> real
    chunk_id mapping and is the sole authority translating any citation
    the model returns back into a real, already-verified chunk.
    """

    ref: str
    content: str


@dataclass
class HistoryTurn:
    """One prior turn of plain conversational context, included only for
    linguistic follow-up resolution (e.g. resolving "it"/"that"). Never a
    source of facts -- see the Step 11 report's conversation-memory
    section. role is "user" or "assistant".
    """

    role: str
    content: str


@dataclass
class GroundedAnswerRequest:
    question: str
    document_context: list[DocumentContextItem]
    history: list[HistoryTurn] = field(default_factory=list)
    # Set only on the single allowed corrective retry (Step 11's bounded
    # citation/structured-output retry) -- a short, specific instruction
    # appended to the user turn explaining what was wrong with the
    # previous attempt. None on a first attempt.
    corrective_note: str | None = None


@dataclass
class GroundedAnswerCitation:
    """A citation exactly as the model returned it -- an unvalidated ref
    string. The caller (ask_service) is the sole authority for turning
    this into a real chunk_id; see the CITATION VALIDATION requirements
    in the Step 11 report. This dataclass never carries a real chunk_id.
    """

    ref: str


@dataclass
class GroundedAnswerResult:
    answer: str
    sufficient: bool
    citations: list[GroundedAnswerCitation]
    model_identifier: str
    input_tokens: int | None
    output_tokens: int | None


@dataclass
class BriefDocumentContextItem:
    """One new/updated document's content, bounded and concatenated from
    its own chunks by the caller (app.modules.briefs.brief_orchestrator) --
    this provider never queries for documents itself, same "not the
    retrieval engine" rule as Q&A. `ref` is a small provider-neutral alias
    for this document, never its real document_id.
    """

    ref: str
    content: str


@dataclass
class BriefCarryForwardItem:
    """One still-possibly-open item from a recent previous brief, given as
    plain context so Claude can judge whether it's resolved or still
    open -- never assumed still valid just because it was true before
    (same principle as Q&A's conversation history: a prior AI output is
    not a trusted fact). `source_ref` is the alias of the document that
    originally grounded it, if any -- part of the same ref namespace as
    `BriefDocumentContextItem.ref`, so the model may re-cite it.
    """

    category: str
    text: str
    priority: int
    source_ref: str | None


@dataclass
class BriefGenerationRequest:
    new_documents: list[BriefDocumentContextItem]
    carry_forward_items: list[BriefCarryForwardItem] = field(default_factory=list)
    corrective_note: str | None = None


@dataclass
class BriefGeneratedItem:
    """An item exactly as the model returned it -- category/text/priority
    plus an UNVALIDATED source ref. The caller is the sole authority for
    turning `source_ref` into a real document_id; see brief_orchestrator's
    citation validation. Never carries a real document_id.
    """

    category: str
    text: str
    priority: int
    source_ref: str | None


@dataclass
class BriefGenerationResult:
    summary: str
    items: list[BriefGeneratedItem]
    model_identifier: str
    input_tokens: int | None
    output_tokens: int | None


@dataclass
class CollaborationMessageContextItem:
    """One chat message, already authorized by the caller
    (app.modules.collaboration.service has verified the requesting user
    is a CURRENT active member of this exact conversation) and bounded to
    a limited window -- this provider never queries messages itself, same
    "not the retrieval engine" rule as document Q&A and the daily brief.
    `ref` is a small provider-neutral alias assigned by the caller, never
    the real message_id UUID. `sender_label` is a display name (or
    "System"), never a raw user_id -- the model is never shown user IDs.
    """

    ref: str
    sender_label: str
    content: str


@dataclass
class CollaborationInsightsRequest:
    messages: list[CollaborationMessageContextItem]
    corrective_note: str | None = None


@dataclass
class CollaborationDecision:
    """A decision exactly as the model returned it -- unvalidated
    source_ref. The caller is the sole authority for turning source_ref
    into a real message_id; see collaboration.service's citation
    validation (mirrors ask_service's chunk-citation validation).
    `confirmed` distinguishes a clearly-settled decision from a possible/
    ambiguous one -- the model must never present ordinary discussion as
    a definitive decision.
    """

    description: str
    confirmed: bool
    source_ref: str | None


@dataclass
class CollaborationActionItem:
    """An action item exactly as the model returned it -- unvalidated
    source_ref. `possible_assignee` is only a name explicitly mentioned in
    the messages, never fabricated; None when ambiguous.
    `due_date` is only set when a date was explicitly stated in the
    messages, never inferred; None otherwise. These remain suggestions --
    the caller never silently creates a company task from one.
    """

    description: str
    possible_assignee: str | None
    due_date: str | None
    source_ref: str | None


@dataclass
class CollaborationInsightsResult:
    summary: str
    decisions: list[CollaborationDecision]
    action_items: list[CollaborationActionItem]
    model_identifier: str
    input_tokens: int | None
    output_tokens: int | None


class LLMProvider(ABC):
    @abstractmethod
    def generate_grounded_answer(self, request: GroundedAnswerRequest) -> GroundedAnswerResult:
        """Raises one of app.core.llm.exceptions' typed errors on any
        failure -- never returns a fabricated or partial answer. Never
        raises the underlying vendor SDK's exception type directly.

        Also used, unmodified, for collaboration conversation Q&A / "find
        relevant discussion" (Step 18): the caller passes each authorized
        message as a DocumentContextItem instead of a document chunk --
        this method's grounded-QA contract (answer strictly from the
        given context, cite by ref, sufficient=false when the context
        doesn't support an answer) is exactly what that capability needs,
        so no new method was added for it.
        """

    @abstractmethod
    def generate_daily_brief(self, request: BriefGenerationRequest) -> BriefGenerationResult:
        """Raises one of app.core.llm.exceptions' typed errors on any
        failure -- never returns a fabricated or partial brief. Same
        grounding discipline as generate_grounded_answer: every item must
        cite a document actually provided in `request`, and the caller
        never trusts `source_ref` without independently validating it.
        """

    @abstractmethod
    def generate_collaboration_insights(
        self, request: CollaborationInsightsRequest
    ) -> CollaborationInsightsResult:
        """Summarize Conversation / Summarize Unread / Extract Decisions /
        Extract Action Items (Step 18) are ONE structured call rather than
        three separate abstract methods -- a summary, its decisions, and
        its action items are naturally produced together from the same
        message window, and a single contract keeps the interface minimal
        while still being a real, citation-validated structure (never
        free-text parsing). Raises one of app.core.llm.exceptions' typed
        errors on any failure -- never returns a fabricated or partial
        result. Same grounding discipline as the other two methods: every
        decision/action item must cite a message actually provided in
        `request`, and the caller never trusts `source_ref` without
        independently validating it against the real, already-authorized
        message set.
        """

