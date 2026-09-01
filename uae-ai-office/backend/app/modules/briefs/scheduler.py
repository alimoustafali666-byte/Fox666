"""Automatic Daily Brief generation for company-local schedules."""

import asyncio
import logging
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal, set_company_context
from app.modules.briefs import brief_orchestrator
from app.modules.tenancy import repository

logger = logging.getLogger(__name__)
_POLL_SECONDS = 30


def run_due_schedules() -> None:
    db = SessionLocal()
    try:
        companies = repository.list_scheduled_companies(db)
    finally:
        db.close()

    for company in companies:
        try:
            local_now = datetime.now(UTC).astimezone(ZoneInfo(company.timezone))
            if local_now.time().replace(tzinfo=None) < company.daily_brief_schedule_time:
                continue
            db = SessionLocal()
            try:
                if not repository.claim_daily_brief_schedule_date(
                    db, company_id=company.id, scheduled_date=local_now.date()
                ):
                    db.rollback()
                    continue
                db.commit()
                set_company_context(db, company.id)
                owner = repository.get_company_owner(db, company.id)
                if owner is None:
                    db.rollback()
                    continue
                brief_orchestrator.generate_brief(
                    db,
                    company_id=company.id,
                    actor_user_id=owner.user_id,
                    ip_address=None,
                    brief_date=local_now.date(),
                )
            except Exception:
                db.rollback()
                logger.exception("Automatic Daily Brief generation failed for company %s", company.id)
            finally:
                db.close()
        except Exception:
            logger.exception("Unable to evaluate Daily Brief schedule for company %s", company.id)


async def scheduler_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await asyncio.to_thread(run_due_schedules)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_POLL_SECONDS)
        except asyncio.TimeoutError:
            pass