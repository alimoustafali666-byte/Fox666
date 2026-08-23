"""Bounded, deterministic knowledge-base search -- no embeddings, no
external service, no company data. Deliberately simple (word-overlap
scoring over a small, fixed article set) rather than reusing
app.modules.documents.retrieval_service, which is a different system
entirely (company documents, pgvector, per-tenant scoping) that this
module must never touch -- see app.modules.support.assistant_service's
module docstring for why that separation matters.
"""

import re

from app.modules.support.articles import ARTICLES, Article

# Unicode-aware, same rationale as app.core.embeddings.fake_provider and
# app.core.llm.fake_provider: an ASCII-only pattern would be blind to
# Arabic queries.
_WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _searchable_text(article: Article, locale: str) -> str:
    if locale == "ar":
        return " ".join([article.title_ar, article.body_ar, *article.keywords_ar])
    return " ".join([article.title_en, article.body_en, *article.keywords_en])


def search_articles(query: str, *, locale: str = "en", limit: int = 10) -> list[Article]:
    """Ranks articles by word overlap with `query` in the given locale,
    highest first; ties broken by declaration order (stable sort). An
    empty/whitespace-only query returns no results rather than "every
    article" -- callers that want a full browse should read ARTICLES
    directly, not call search with an empty string.
    """
    query_words = _words(query)
    if not query_words:
        return []

    scored: list[tuple[int, Article]] = []
    for article in ARTICLES:
        overlap = len(query_words & _words(_searchable_text(article, locale)))
        if overlap > 0:
            scored.append((overlap, article))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [article for _, article in scored[:limit]]


def articles_by_category(category: str) -> list[Article]:
    return [a for a in ARTICLES if a.category == category]

