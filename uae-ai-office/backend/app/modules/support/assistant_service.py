"""The Technical Support AI Assistant -- help using UAE AI Office itself,
never a second way to ask about company business data.

CRITICAL ARCHITECTURAL BOUNDARY (Step 17): this module must never import
app.modules.conversations, app.modules.documents.retrieval_service, or
app.core.embeddings. Its only possible inputs are:

  1. Knowledge-base articles (app.modules.support.kb_search), which are
     static, code-backed product-help content -- never a company's own
     documents.
  2. A small, explicit-allowlist "diagnostics" snippet
     (app.modules.support.diagnostics), built by re-fetching a
     document/project through the SAME company-scoped, RLS-respecting
     service getters the rest of the app already uses -- never raw
     database access, and never document content.

No conversation history is read or persisted here: every question is
answered statelessly, in isolation, so there is no path by which a prior
Ask Your Business exchange -- or a prior Support Assistant exchange --
could leak into a later request or another company's session.

Reuses the exact same LLMProvider.generate_grounded_answer grounding/
citation-validation discipline as Ask Your Business (see
app.modules.conversations.ask_service's module docstring) -- a citation
is only ever trusted if it matches a ref this module itself handed the
model in THIS request's document_context.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.llm.exceptions import (
    LLMAuthenticationError,
    LLMConfigurationError,
    LLMError,
    LLMMalformedOutputError,
    LLMOperationError,
    LLMUnavailable,
)
from app.core.llm.factory import get_llm_provider
from app.core.llm.provider import DocumentContextItem, GroundedAnswerRequest
from app.modules.audit_log.service import record_audit_event
from app.modules.auth.service import TenantContext
from app.modules.support.articles import ARTICLES_BY_SLUG
from app.modules.support.diagnostics import DiagnosticsInput, build_diagnostics
from app.modules.support.exceptions import (
    BlankSupportQuestionError,
    SupportAssistantRateLimitedError,
    SupportAssistantUnavailableError,
)
from app.modules.support.kb_search import search_articles
from app.modules.support.rate_limit import assistant_ask_rate_limiter
from app.modules.support.schemas import SupportAssistantAskResponse, SupportAssistantCitation

_DIAGNOSTICS_REF = "diagnostics"

_INSUFFICIENT_TEXT_EN = (
    "I couldn't find that in our help content. Try rephrasing your question, or create a "
    "support ticket and our team will help."
)
_INSUFFICIENT_TEXT_AR = (
    "لم أجد ذلك في محتوى المساعدة لدينا. جرّب إعادة صياغة سؤالك، أو أنشئ تذكرة دعم وسيساعدك فريقنا."
)


def ask_support_assistant(
    db: Session,
    *,
    context: TenantContext,
    question: str,
    locale: str,
    diagnostics_input: DiagnosticsInput | None,
    ip_address: str | None,
) -> SupportAssistantAskResponse:
    question = question.strip()
    if not question:
        raise BlankSupportQuestionError("Question must not be blank.")

    if assistant_ask_rate_limiter.is_locked(str(context.user.id)):
        raise SupportAssistantRateLimitedError(
            "Too many support questions asked recently. Please try again in a moment."
        )
    assistant_ask_rate_limiter.record_failure(str(context.user.id))

    matched = search_articles(question, locale=locale, limit=settings.support_kb_top_k)
    document_context = [
        DocumentContextItem(
            ref=article.slug,
            content=article.body_ar if locale == "ar" else article.body_en,
        )
        for article in matched
    ]

    diagnostics: dict = {}
    if diagnostics_input is not None:
        diagnostics = build_diagnostics(db, context=context, data=diagnostics_input)
        if diagnostics:
            document_context.append(
                DocumentContextItem(ref=_DIAGNOSTICS_REF, content=_format_diagnostics(diagnostics))
            )

    if not document_context:
        _record_ask_event(
            db, context=context, ip_address=ip_address, kb_hit=False, sufficient=False
        )
        db.commit()
        return SupportAssistantAskResponse(
            answer=_INSUFFICIENT_TEXT_AR if locale == "ar" else _INSUFFICIENT_TEXT_EN,
            sufficient=False,
            citations=[],
            used_diagnostics=False,
        )

    provider = get_llm_provider()
    request = GroundedAnswerRequest(question=question, document_context=document_context, history=[])
    try:
        result = provider.generate_grounded_answer(request)
    except LLMMalformedOutputError:
        _record_ask_event(db, context=context, ip_address=ip_address, kb_hit=True, sufficient=False)
        db.commit()
        return SupportAssistantAskResponse(
            answer=_INSUFFICIENT_TEXT_AR if locale == "ar" else _INSUFFICIENT_TEXT_EN,
            sufficient=False,
            citations=[],
            used_diagnostics=bool(diagnostics),
        )
    except (LLMAuthenticationError, LLMConfigurationError, LLMUnavailable, LLMOperationError) as exc:
        raise SupportAssistantUnavailableError(
            "The support assistant is temporarily unavailable."
        ) from exc
    except LLMError as exc:  # last-resort safety net for any unmapped LLMError subclass
        raise SupportAssistantUnavailableError(
            "The support assistant is temporarily unavailable."
        ) from exc

    valid_refs = {item.ref for item in document_context}
    citations: list[SupportAssistantCitation] = []
    used_diagnostics = False
    for citation in result.citations:
        if citation.ref == _DIAGNOSTICS_REF:
            if citation.ref in valid_refs:
                used_diagnostics = True
            continue  # diagnostics is context, not a citable help article
        if citation.ref not in valid_refs:
            continue  # never trust a fabricated ref -- same discipline as ask_service
        article = ARTICLES_BY_SLUG.get(citation.ref)
        if article is None:
            continue
        citations.append(
            SupportAssistantCitation(
                article_slug=article.slug,
                title=article.title_ar if locale == "ar" else article.title_en,
            )
        )

    sufficient = result.sufficient and (len(citations) > 0 or used_diagnostics)

    _record_ask_event(
        db, context=context, ip_address=ip_address, kb_hit=len(matched) > 0, sufficient=sufficient
    )
    db.commit()

    if not sufficient:
        return SupportAssistantAskResponse(
            answer=_INSUFFICIENT_TEXT_AR if locale == "ar" else _INSUFFICIENT_TEXT_EN,
            sufficient=False,
            citations=[],
            used_diagnostics=False,
        )

    return SupportAssistantAskResponse(
        answer=result.answer,
        sufficient=True,
        citations=citations,
        used_diagnostics=used_diagnostics,
    )


def _format_diagnostics(diagnostics: dict) -> str:
    lines = [f"{key}: {value}" for key, value in diagnostics.items()]
    return "Diagnostic information for this session:\n" + "\n".join(lines)


def _record_ask_event(
    db: Session, *, context: TenantContext, ip_address: str | None, kb_hit: bool, sufficient: bool
) -> None:
    record_audit_event(
        db,
        company_id=context.company_id,
        actor_user_id=context.user.id,
        action="support.assistant_asked",
        resource_type="support_assistant",
        resource_id=None,
        metadata={"kb_hit": kb_hit, "sufficient": sufficient},
        ip_address=ip_address,
    )

