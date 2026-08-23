import uuid
from datetime import UTC, date, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.modules.briefs.models import BriefItem, DailyBrief
from app.modules.documents.models import Document


def create_daily_brief(
    db: Session,
    *,
    id: uuid.UUID,
    company_id: uuid.UUID,
    generated_by: uuid.UUID,
    brief_date: date,
    summary: str,
) -> DailyBrief:
    # generated_at set explicitly in Python, not left to the column's
    # `now()` server_default -- see brief_orchestrator's identical note on
    # regeneration; this keeps creation and regeneration consistent.
    brief = DailyBrief(
        id=id, company_id=company_id, generated_by=generated_by, brief_date=brief_date, summary=summary,
        generated_at=datetime.now(UTC),
    )
    db.add(brief)
    db.flush()
    return brief


def get_daily_brief_by_date(
    db: Session, *, company_id: uuid.UUID, brief_date: date
) -> DailyBrief | None:
    return db.execute(
        select(DailyBrief).where(
            DailyBrief.company_id == company_id, DailyBrief.brief_date == brief_date
        )
    ).scalar_one_or_none()


def get_latest_daily_brief(db: Session, *, company_id: uuid.UUID) -> DailyBrief | None:
    """The single most recent brief regardless of date -- what
    `GET /v1/briefs` (no `date` query param) returns. Distinct from
    get_previous_daily_brief below, which deliberately excludes a given
    date and is only used internally by brief_orchestrator's "since last
    brief" window calculation.
    """
    return db.execute(
        select(DailyBrief)
        .where(DailyBrief.company_id == company_id)
        .order_by(DailyBrief.brief_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def get_previous_daily_brief(
    db: Session, *, company_id: uuid.UUID, before_date: date
) -> DailyBrief | None:
    """The most recent brief strictly BEFORE `before_date` -- used as the
    "since last brief" cutoff. Deliberately excludes `before_date` itself
    so that regenerating today's own brief re-uses the same window (since
    the previous day's brief) rather than narrowing to "since my own
    last regeneration attempt".
    """
    return db.execute(
        select(DailyBrief)
        .where(DailyBrief.company_id == company_id, DailyBrief.brief_date < before_date)
        .order_by(DailyBrief.brief_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def list_daily_briefs(
    db: Session,
    *,
    company_id: uuid.UUID,
    limit: int,
    cursor: tuple[datetime, uuid.UUID] | None = None,
) -> list[DailyBrief]:
    query = select(DailyBrief).where(DailyBrief.company_id == company_id)
    if cursor is not None:
        cursor_generated_at, cursor_id = cursor
        query = query.where(
            or_(
                DailyBrief.generated_at < cursor_generated_at,
                and_(DailyBrief.generated_at == cursor_generated_at, DailyBrief.id < cursor_id),
            )
        )
    query = query.order_by(DailyBrief.generated_at.desc(), DailyBrief.id.desc()).limit(limit)
    return list(db.execute(query).scalars())


def delete_brief_items(db: Session, *, company_id: uuid.UUID, brief_id: uuid.UUID) -> None:
    """Used only when regenerating an already-existing same-day brief --
    called after the new items have already been generated and validated
    in memory (see brief_orchestrator), immediately before inserting the
    replacement set in the same transaction, mirroring documents'
    replace-chunks-atomically pattern from Step 9.
    """
    for item in db.execute(
        select(BriefItem).where(BriefItem.company_id == company_id, BriefItem.brief_id == brief_id)
    ).scalars():
        db.delete(item)
    db.flush()


def create_brief_items(
    db: Session,
    *,
    company_id: uuid.UUID,
    brief_id: uuid.UUID,
    items: list[dict],
) -> list[BriefItem]:
    """`items` must already be fully validated by the caller (category is
    one of BRIEF_ITEM_CATEGORIES, source_document_id -- if set -- belongs
    to this company and was actually part of this run's context). This
    function trusts that and does not re-validate.
    """
    rows = [
        BriefItem(
            company_id=company_id,
            brief_id=brief_id,
            category=item["category"],
            text=item["text"],
            source_document_id=item.get("source_document_id"),
            priority=item["priority"],
        )
        for item in items
    ]
    db.add_all(rows)
    db.flush()
    return rows


def list_brief_items(db: Session, *, company_id: uuid.UUID, brief_id: uuid.UUID) -> list[BriefItem]:
    return list(
        db.execute(
            select(BriefItem)
            .where(BriefItem.company_id == company_id, BriefItem.brief_id == brief_id)
            .order_by(BriefItem.priority.asc(), BriefItem.created_at.asc())
        ).scalars()
    )


def get_brief_item_by_id(db: Session, *, company_id: uuid.UUID, item_id: uuid.UUID) -> BriefItem | None:
    """Used by app.modules.tasks.service to re-validate a daily_brief-
    sourced task reference at creation time -- company_id scoping here
    is the same defense-in-depth on top of RLS as every other
    get_by_id in this app.
    """
    return db.execute(
        select(BriefItem).where(BriefItem.id == item_id, BriefItem.company_id == company_id)
    ).scalar_one_or_none()


def list_documents_since(
    db: Session,
    *,
    company_id: uuid.UUID,
    since: datetime | None,
    limit: int,
) -> list[Document]:
    """Only fully `processed` documents (there's no usable extracted
    content otherwise) that were created or updated after `since` --
    `since=None` means "no prior brief", i.e. every processed document is
    in scope for the very first brief. Ordered newest-first and capped at
    `limit` (settings.brief_max_documents_per_run) -- this is the bound
    that keeps brief generation cost proportional to what's new, never to
    the whole historical corpus, per the approved architecture.
    """
    query = select(Document).where(
        Document.company_id == company_id,
        Document.status == "processed",
        Document.deleted_at.is_(None),
    )
    if since is not None:
        query = query.where(Document.updated_at > since)
    query = query.order_by(Document.updated_at.desc()).limit(limit)
    return list(db.execute(query).scalars())


def list_recent_open_items(
    db: Session,
    *,
    company_id: uuid.UUID,
    before_date: date,
    lookback_briefs: int,
    max_items: int,
) -> list[BriefItem]:
    """Non-"new_information" items (pending_action/follow_up/
    potential_issue -- the categories that can meaningfully still be
    "open") from the most recent `lookback_briefs` briefs strictly before
    `before_date`, newest first, capped at `max_items`. Excludes
    `before_date` itself so regenerating today's own brief never carries
    its own items into itself. Purely context for the next generation
    call to judge resolved-vs-still-open; never assumed still valid by
    this function itself.
    """
    recent_brief_ids = list(
        db.execute(
            select(DailyBrief.id)
            .where(DailyBrief.company_id == company_id, DailyBrief.brief_date < before_date)
            .order_by(DailyBrief.brief_date.desc())
            .limit(lookback_briefs)
        ).scalars()
    )
    if not recent_brief_ids:
        return []

    return list(
        db.execute(
            select(BriefItem)
            .where(
                BriefItem.company_id == company_id,
                BriefItem.brief_id.in_(recent_brief_ids),
                BriefItem.category != "new_information",
            )
            .order_by(BriefItem.priority.asc(), BriefItem.created_at.desc())
            .limit(max_items)
        ).scalars()
    )

