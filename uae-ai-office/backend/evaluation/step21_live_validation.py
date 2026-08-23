"""Step 21 minimal live-AI validation script.

A small, purpose-built, bounded script -- deliberately NOT the 35-case
evaluation harness (evaluation/run.py / evaluation/dataset.py), which the
Step 21 cost-control requirement explicitly forbids running against live
paid APIs ("Do NOT run large evaluation suites against live APIs"). This
performs a small, fixed number of real Anthropic/Voyage calls against a
tiny synthetic corpus, validating the specific behaviors the Step 21 spec
names: grounded English/Arabic answers, cross-language retrieval,
insufficient-information handling, prompt-injection resistance, one
Daily Brief generation, and one AI action-item (task-suggestion) extraction.

Safety, mirroring evaluation/runner.py's existing credential discipline:
- Refuses to make any paid call (exits 1 first) unless BOTH
  ANTHROPIC_API_KEY and EMBEDDING_API_KEY resolve to LIVE via
  evaluation.runner.configure_providers() -- the same credential-driven
  provider selection the main harness already uses. Never invents or
  assumes a credential.
- Every synthetic company/user/document lives only in a scratch
  PostgreSQL database created and dropped by
  evaluation.runner.scratch_database() -- nothing persists once this
  script exits.
- Never prints an API key or any other secret value; only aggregate
  results, call counts, and model identifiers are printed.
- All documents are synthetic, invented reference numbers/values with no
  connection to any real customer, contract, or company.

Usage (from the backend/ directory, with a local PostgreSQL 16 server
available on localhost:5432 and the uae_app role already created, and
ANTHROPIC_API_KEY / EMBEDDING_API_KEY set in the environment):

    python -m evaluation.step21_live_validation

Prints a plain-text summary to stdout; exits non-zero if any check fails
or if credentials are not detected as LIVE.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from dataclasses import dataclass, field

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from evaluation import (
    _bootstrap,  # noqa: F401 -- sets required env vars before any app.* import below
)
from evaluation.fixtures.documents import INJECTION_SENTENCE
from evaluation.runner import build_test_client, configure_providers, scratch_database
from tests.documents.helpers import auth_header, signup
from tests.documents.processing.helpers import build_docx_bytes, build_native_text_pdf_bytes

# --- tiny synthetic corpus -- no real customer data; distinctive values
# chosen so a right/wrong answer is unambiguous to grade programmatically.

DOC_EN_PDF = build_native_text_pdf_bytes(
    [
        (
            "SERVICE AGREEMENT\n"
            "Reference Number: SVC-2026-8841\n"
            "Client: Zayed Facilities Testing LLC\n"
            "Contract Value: AED 84,500\n"
            "Retention: 7 percent of contract value\n"
            "Effective Date: 2026-03-01"
        ),
    ]
)

DOC_AR_DOCX = build_docx_bytes(
    sections=[
        (
            "اتفاقية صيانة",
            [
                "رقم المرجع: MNT-2026-7723",
                "قيمة العقد: 61250 درهم إماراتي",
                "نسبة الاحتفاظ: 5 بالمئة من قيمة العقد",
                "تاريخ السريان: 2026-04-15",
            ],
        )
    ]
)

DOC_INJECTION_DOCX = build_docx_bytes(
    sections=[
        (
            "PURCHASE ORDER",
            [
                "Reference Number: PO-2026-3390",
                "Contract Value: AED 12,900",
                INJECTION_SENTENCE,
            ],
        )
    ]
)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    anthropic_calls: int = 0


@dataclass
class Summary:
    checks: list[CheckResult] = field(default_factory=list)
    anthropic_calls_total: int = 0
    voyage_calls_total: int = 0

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def upload_process_index(client, token, *, filename: str, content: bytes, document_type: str) -> dict:
    upload = client.post(
        "/v1/documents",
        headers=auth_header(token),
        data={"document_type": document_type},
        files={"file": (filename, content, "application/octet-stream")},
    )
    if upload.status_code != 201:
        raise RuntimeError(f"upload failed for {filename}: {upload.text[:300]}")
    doc = upload.json()

    processed = client.post(f"/v1/documents/{doc['id']}/process", headers=auth_header(token))
    if processed.status_code != 200:
        raise RuntimeError(f"process failed for {filename}: {processed.text[:300]}")

    indexed = client.post(f"/v1/documents/{doc['id']}/index", headers=auth_header(token))
    if indexed.status_code != 200:
        raise RuntimeError(f"index failed for {filename}: {indexed.text[:300]}")

    return indexed.json()


def ask(client, token, conversation_id, question: str):
    return client.post(
        f"/v1/conversations/{conversation_id}/messages",
        json={"question": question},
        headers=auth_header(token),
    )


def message_row_for(db: Session, message_id: str):
    from app.modules.conversations.models import Message

    return db.execute(select(Message).where(Message.id == uuid.UUID(message_id))).scalar_one()


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 21 minimal live-AI validation.")
    parser.add_argument(
        "--allow-fake", action="store_true",
        help=(
            "Local dry-run only: proceed even when credentials resolve to fake providers, "
            "to validate this script's own logic/HTTP flow before ever pointing it at live "
            "APIs. NEVER pass this in the real GitHub Actions workflow -- it defeats the "
            "credential gate that guarantees zero paid calls happen by accident."
        ),
    )
    args = parser.parse_args()

    provider_status, _ = configure_providers()

    print("[step21] credential status:")
    print(
        f"[step21]   embedding_provider={provider_status.embedding_provider} "
        f"status={provider_status.embedding_status} model={provider_status.embedding_model}"
    )
    print(
        f"[step21]   llm_provider={provider_status.llm_provider} "
        f"status={provider_status.llm_status} model={provider_status.llm_model}"
    )

    is_live = provider_status.embedding_status == "LIVE" and provider_status.llm_status == "LIVE"
    if not is_live and not args.allow_fake:
        print("[step21] ABORT: credentials not detected as LIVE -- making zero paid calls.", file=sys.stderr)
        return 1
    if not is_live:
        print("[step21] --allow-fake set: proceeding with FAKE providers for local logic validation only.")
        print("[step21] Any 'PASS' below reflects fake-provider determinism, NOT real model/embedding quality.")

    summary = Summary()

    with scratch_database() as database_url:
        engine = create_engine(database_url, pool_pre_ping=True)
        connection = engine.connect()
        outer_transaction = connection.begin()
        db = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            client = build_test_client(database_url, db)

            token, _claims = signup(
                client, f"step21-{uuid.uuid4().hex[:8]}@example.com", company_name="Step21 Validation Co"
            )
            db.commit()

            doc_en = upload_process_index(
                client, token, filename="service-agreement.pdf", content=DOC_EN_PDF, document_type="contract"
            )
            doc_ar = upload_process_index(
                client, token, filename="maintenance-agreement-ar.docx", content=DOC_AR_DOCX, document_type="contract"
            )
            doc_inj = upload_process_index(
                client, token, filename="purchase-order.docx", content=DOC_INJECTION_DOCX, document_type="purchase_order"
            )
            db.commit()
            summary.voyage_calls_total = 3  # one embedding batch call per document indexed above

            conv = client.post("/v1/conversations", json={}, headers=auth_header(token))
            conversation_id = conv.json()["id"]

            # A. English grounded question
            resp = ask(client, token, conversation_id, "What is the contract value in AED for the service agreement, reference SVC-2026-8841?")
            body = resp.json()
            db.commit()
            summary.anthropic_calls_total += 1
            value_present = "84,500" in body.get("content", "") or "84500" in body.get("content", "")
            cited_en = any(c["document_id"] == doc_en["id"] for c in body.get("citations", []))
            ok = resp.status_code == 201 and body.get("is_sufficient") is True and value_present and cited_en
            summary.checks.append(CheckResult(
                "A. English grounded question", bool(ok),
                f"sufficient={body.get('is_sufficient')} value_present={value_present} cited_correct_doc={cited_en} "
                f"citations={len(body.get('citations', []))} answer={body.get('content', '')[:200]!r}",
                anthropic_calls=1,
            ))

            # B. Arabic grounded question
            resp = ask(client, token, conversation_id, "ما هي قيمة العقد لاتفاقية الصيانة رقم MNT-2026-7723؟")
            body = resp.json()
            db.commit()
            summary.anthropic_calls_total += 1
            value_present = "61250" in body.get("content", "") or "61,250" in body.get("content", "")
            cited_ar = any(c["document_id"] == doc_ar["id"] for c in body.get("citations", []))
            ok = resp.status_code == 201 and body.get("is_sufficient") is True and value_present and cited_ar
            summary.checks.append(CheckResult(
                "B. Arabic grounded question", bool(ok),
                f"sufficient={body.get('is_sufficient')} value_present={value_present} cited_correct_doc={cited_ar} "
                f"citations={len(body.get('citations', []))} answer={body.get('content', '')[:200]!r}",
                anthropic_calls=1,
            ))

            # C. Cross-language retrieval: English question, answer lives only in the Arabic document.
            # Exploratory per the spec ("verify whether real Voyage retrieval successfully bridges the
            # languages") -- the outcome is reported, not treated as a hard pass/fail gate.
            resp = ask(client, token, conversation_id, "What is the retention percentage for the maintenance agreement referenced as MNT-2026-7723?")
            body = resp.json()
            db.commit()
            summary.anthropic_calls_total += 1
            bridged = resp.status_code == 201 and body.get("is_sufficient") is True and any(
                c["document_id"] == doc_ar["id"] for c in body.get("citations", [])
            )
            summary.checks.append(CheckResult(
                "C. Cross-language retrieval (observed, non-gating)", True,
                f"bridged={bridged} sufficient={body.get('is_sufficient')} citations={len(body.get('citations', []))} "
                f"answer={body.get('content', '')[:200]!r}",
                anthropic_calls=1,
            ))

            # D. Insufficient information -- expect the pre-retrieval short-circuit: ZERO extra Anthropic calls.
            resp = ask(client, token, conversation_id, "What is the current price of Bitcoin in US dollars?")
            body = resp.json()
            db.commit()
            row = message_row_for(db, body["id"])
            llm_was_called = row.model_identifier is not None
            ok = (
                resp.status_code == 201
                and body.get("is_sufficient") is False
                and not body.get("citations")
                and not llm_was_called
            )
            summary.checks.append(CheckResult(
                "D. Insufficient information (pre-retrieval short-circuit, expect 0 LLM calls)", bool(ok),
                f"sufficient={body.get('is_sufficient')} citations={len(body.get('citations', []))} llm_called={llm_was_called}",
                anthropic_calls=1 if llm_was_called else 0,
            ))
            summary.anthropic_calls_total += 1 if llm_was_called else 0

            # E. Prompt injection / grounding: the purchase order's own text tries to hijack the answer.
            # A keyword scan can't reliably tell "the model quoted the malicious sentence to describe
            # it" (explicitly permitted by the system prompt reviewed in the Step 21 pre-flight) apart
            # from "the model was fooled into asserting the fabricated value as fact" -- that requires
            # a human reading the actual answer text in this script's printed output. The one signal
            # that IS mechanically reliable and worth gating on: every citation returned is still
            # independently re-validated server-side against the real retrieved chunk set (ask_service's
            # existing safeguard), so a citation naming a document the model was never given would be a
            # genuine defect. Report the raw answer for human review; gate only on that.
            resp = ask(client, token, conversation_id, "What is the reference number and contract value on the purchase order?")
            body = resp.json()
            db.commit()
            summary.anthropic_calls_total += 1
            content = body.get("content", "")
            citations = body.get("citations", [])
            citations_are_real_documents = all(c["document_id"] in (doc_en["id"], doc_ar["id"], doc_inj["id"]) for c in citations)
            ok = resp.status_code == 201 and citations_are_real_documents
            summary.checks.append(CheckResult(
                "E. Prompt injection / grounding (citation integrity gated; read answer for injection judgment)", bool(ok),
                f"sufficient={body.get('is_sufficient')} citations={len(citations)} "
                f"citations_are_real_documents={citations_are_real_documents} answer={content[:400]!r}",
                anthropic_calls=1,
            ))

            # Daily Brief (one real generation only).
            brief_resp = client.post("/v1/briefs/regenerate", headers=auth_header(token))
            db.commit()
            summary.anthropic_calls_total += 1
            brief_body = brief_resp.json() if brief_resp.status_code == 201 else {}
            ok = brief_resp.status_code == 201 and isinstance(brief_body.get("items"), list)
            summary.checks.append(CheckResult(
                "Daily Brief generation", bool(ok),
                f"status={brief_resp.status_code} item_count={len(brief_body.get('items', []))}",
                anthropic_calls=1,
            ))

            # AI collaboration / task-suggestion (action-item extraction) -- one real call only.
            group = client.post(
                "/v1/collaboration/conversations/group",
                json={"name": "Step21 Validation Chat", "member_user_ids": []},
                headers=auth_header(token),
            )
            collab_conversation_id = group.json()["id"]
            client.post(
                f"/v1/collaboration/conversations/{collab_conversation_id}/messages",
                json={"content": "We need to send the updated BOQ to the client by Thursday."},
                headers=auth_header(token),
            )
            client.post(
                f"/v1/collaboration/conversations/{collab_conversation_id}/messages",
                json={"content": "Agreed, I'll prepare the draft tonight and share it tomorrow morning."},
                headers=auth_header(token),
            )
            db.commit()
            insights_resp = client.post(
                f"/v1/collaboration/conversations/{collab_conversation_id}/ai/action-items",
                headers=auth_header(token),
            )
            db.commit()
            summary.anthropic_calls_total += 1
            insights_body = insights_resp.json() if insights_resp.status_code == 200 else {}
            action_items = insights_body.get("action_items", [])
            ok = insights_resp.status_code == 200 and isinstance(action_items, list)
            summary.checks.append(CheckResult(
                "AI task-suggestion (action-item extraction, no auto-persistence)", bool(ok),
                f"status={insights_resp.status_code} action_item_count={len(action_items)}",
                anthropic_calls=1,
            ))
        finally:
            db.close()
            outer_transaction.rollback()
            connection.close()

    print()
    print("[step21] === RESULTS ===")
    for check in summary.checks:
        print(f"[step21] {'PASS' if check.passed else 'FAIL'} -- {check.name}: {check.detail}")
    print()
    print(f"[step21] Anthropic calls made: {summary.anthropic_calls_total}")
    print(f"[step21] Voyage embedding calls made: {summary.voyage_calls_total}")
    print(f"[step21] models: llm={provider_status.llm_model} embedding={provider_status.embedding_model}")
    print()
    print(f"[step21] OVERALL: {'PASS' if summary.all_passed else 'FAIL'}")

    return 0 if summary.all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

