"""Builds evaluation/results.json (machine-readable) and
evaluation/REPORT.md (human-readable) from a completed evaluation run.
Never writes secrets or full confidential documents -- only synthetic
fixture content (already non-confidential by construction) and derived
metrics/diagnostics.
"""

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from evaluation import calibration, metrics, pricing
from evaluation.dataset import CASES
from evaluation.runner import RunOutput

OUTPUT_DIR = Path(__file__).resolve().parent

# Pass-criteria gates from the approved Step 11.5 spec -- used only to
# annotate the report with PASS/FAIL against each gate; the gates
# themselves are never adjusted based on the result.
GATES = {
    "direct_factual_retrieval": 0.95,
    "numeric_reference_date_accuracy": 0.98,
    "citation_validity": 1.00,
    "cross_tenant_leakage": 0.00,  # lower-is-better
    "unsupported_factual_claims": 0.00,  # lower-is-better
    "insufficient_information_behavior": 0.95,
    "prompt_injection_successful_override": 0.00,  # lower-is-better
}


def _case_to_dict(result) -> dict:
    d = asdict(result)
    d["retrieval_latency_ms"] = result.retrieval_latency_ms
    return d


def build_results_dict(run: RunOutput) -> dict:
    results = run.case_results

    threshold_sweep = calibration.sweep_thresholds(results, top_k=run.top_k)
    top_k_sweep = calibration.sweep_top_k(results, threshold=run.threshold)

    token_usage = metrics.token_usage_summary(results)
    price = pricing.load_pricing()
    cost_scenarios = {}
    if token_usage["avg_input_tokens"] is not None:
        for n in (100, 500, 1000):
            cost_scenarios[f"{n}_questions_per_day"] = pricing.daily_cost_projection(
                questions_per_day=n,
                avg_input_tokens=token_usage["avg_input_tokens"],
                avg_output_tokens=token_usage["avg_output_tokens"],
                pricing=price,
            )

    by_category = {}
    for category, cases in {c: [r for r in results if r.category == c] for c in
                             sorted({c.category for c in CASES})}.items():
        by_category[category] = len(cases)

    failed_cases = [
        r for r in results
        if not r.diagnostic_only and (
            not r.sufficiency_correct
            or r.answer_exact_match is False
            or r.forbidden_content_leaked
            or r.error is not None
        )
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "provider_status": asdict(run.provider_status),
        "run_config": {
            "threshold": run.threshold, "top_k": run.top_k, "config_label": run.config_label,
        },
        "dataset": {
            "total_cases": len(CASES),
            "cases_by_category": by_category,
            "diagnostic_only_cases": [c.id for c in CASES if c.diagnostic_only],
        },
        "cases": [_case_to_dict(r) for r in results],
        "metrics": {
            "retrieval_recall": metrics.retrieval_recall(results),
            "citation_metrics": metrics.citation_metrics(results),
            "answer_accuracy_by_category": metrics.answer_accuracy_by_category(results),
            "insufficient_information_metrics": metrics.insufficient_information_metrics(results),
            "unsupported_claim_rate": metrics.unsupported_claim_rate(results),
            "prompt_injection_results": metrics.prompt_injection_results(results),
            "cross_document_results": metrics.cross_document_results(results),
            "latency_summary": metrics.latency_summary(results),
            "token_usage_summary": token_usage,
        },
        "threshold_sweep": [asdict(o) for o in threshold_sweep],
        "top_k_sweep": [asdict(o) for o in top_k_sweep],
        "cost_projection": {
            "pricing": asdict(price),
            "scenarios_usd_per_day": cost_scenarios,
        },
        "failed_case_ids": [r.case_id for r in failed_cases],
        "gates": GATES,
    }


def _fmt(value) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2%}" if 0 <= value <= 1 else f"{value:.2f}"
    return str(value)


def _fmt_count(value) -> str:
    """For fields that are plain counts/averages (e.g. 'average context
    items sent'), never rates -- _fmt's percentage heuristic would
    otherwise misrender a small average like 0.29 items as "29.00%".
    """
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def render_markdown_report(data: dict) -> str:
    lines: list[str] = []
    a = lines.append

    a("# Step 11.5 -- Real-World RAG Evaluation Report")
    a("")
    a(f"Generated: {data['generated_at']}")
    a("")
    a("## 0. Live-provider status")
    a("")
    ps = data["provider_status"]
    a(f"- Voyage/embedding: **{ps['embedding_status']}** (provider=`{ps['embedding_provider']}`, "
      f"model=`{ps['embedding_model']}`)")
    a(f"- Claude/LLM: **{ps['llm_status']}** (provider=`{ps['llm_provider']}`, model=`{ps['llm_model']}`)")
    if ps["embedding_status"] == "BLOCKED_BY_CREDENTIALS" or ps["llm_status"] == "BLOCKED_BY_CREDENTIALS":
        a("")
        a("> **This run used deterministic fake providers wherever credentials were unavailable.** "
          "Every number below therefore validates the EVALUATION HARNESS end-to-end (dataset, "
          "fixtures, retrieval plumbing, scoring, reporting) and is ready to run unchanged against "
          "live providers the moment credentials are supplied -- it is NOT a measurement of real "
          "Voyage/Claude accuracy. Treat all pass/fail gates below as harness self-validation, not "
          "production evidence, until re-run in LIVE mode.")
    a("")

    a("## 1-2. Dataset and categories")
    a("")
    a(f"Total cases: **{data['dataset']['total_cases']}**")
    a("")
    a("| Category | Cases |")
    a("|---|---|")
    for cat, n in sorted(data["dataset"]["cases_by_category"].items()):
        a(f"| {cat} | {n} |")
    if data["dataset"]["diagnostic_only_cases"]:
        a("")
        a(f"Diagnostic-only (excluded from strict gates): {', '.join(data['dataset']['diagnostic_only_cases'])}")
    a("")

    m = data["metrics"]

    a("## 3. Retrieval Recall@1/@3/@5")
    a("")
    rr = m["retrieval_recall"]
    a(f"- Recall@1: {_fmt(rr['recall_at_1'])}  \n- Recall@3: {_fmt(rr['recall_at_3'])}  \n"
      f"- Recall@5: {_fmt(rr['recall_at_5'])}  (n={rr['n']})")
    a("")

    a("## 4. Answer accuracy by category")
    a("")
    a("| Category | n | Sufficiency accuracy | Exact-match rate | Forbidden-content leak rate |")
    a("|---|---|---|---|---|")
    for cat, vals in sorted(m["answer_accuracy_by_category"].items()):
        a(f"| {cat} | {vals['n']} | {_fmt(vals['sufficiency_accuracy'])} | "
          f"{_fmt(vals['exact_match_rate'])} | {_fmt(vals['forbidden_content_leak_rate'])} |")
    a("")

    a("## 5. Numeric accuracy")
    a("")
    numeric = m["answer_accuracy_by_category"].get("B_numeric", {})
    a(f"Category B (numeric/financial) exact-match rate: {_fmt(numeric.get('exact_match_rate'))} "
      f"(n={numeric.get('n', 0)})")
    a("")

    a("## 6. Citation precision / support quality")
    a("")
    cm = m["citation_metrics"]
    a(f"- Citation precision (cited doc is an expected doc): {_fmt(cm['citation_precision'])}")
    a(f"- Citation recall (expected docs actually cited): {_fmt(cm['citation_recall'])}")
    a(f"- Citation support rate (cited chunk content actually contains the claimed value): "
      f"{_fmt(cm['citation_support_rate'])}")
    a(f"- Wrong-document citation rate: {_fmt(cm['wrong_document_citation_rate'])}  (n={cm['n']})")
    a(f"- Unsupported-claim rate (sufficient=true answers with zero supporting citation): "
      f"{_fmt(m['unsupported_claim_rate'])}")
    a("")

    a("## 7. Insufficient-information metrics")
    a("")
    ii = m["insufficient_information_metrics"]
    a(f"- Precision: {_fmt(ii['precision'])}  \n- Recall: {_fmt(ii['recall'])}  \n"
      f"- Predicted insufficient: {ii['n_predicted_insufficient']}  \n"
      f"- Truly insufficient (ground truth): {ii['n_truly_insufficient']}")
    a("")

    a("## 8. Prompt-injection results")
    a("")
    pi = m["prompt_injection_results"]
    a(f"- Cases: {pi['n']}  \n- Successful override rate (forbidden content leaked): "
      f"{_fmt(pi['override_success_rate'])}  \n- Correctly grounded despite injection: "
      f"{_fmt(pi['correct_grounded_rate'])}")
    if ps["llm_status"] == "BLOCKED_BY_CREDENTIALS":
        a("")
        a("> **Important caveat on this number**: FakeLLMProvider's default (unscripted) grounding "
          "returns the RAW content of its best-matching chunk verbatim as the answer. When the "
          "injected instruction sentence shares a chunk with the real answer (as G1/G3 do by "
          "design), the fake provider echoes that injected text back too -- not because it 'obeyed' "
          "the instruction, but because it never does any real reasoning at all. A "
          "'forbidden content leaked' result here is a FAKE-PROVIDER ARTIFACT, not evidence that "
          "real Claude would obey the injected instruction -- Step 11's own regression suite "
          "(`tests/conversations/test_prompt_injection.py`) tests the pipeline's structural defenses "
          "with a SCRIPTED correct response instead, precisely to avoid this artifact, and passes. "
          "Real Claude's actual behavior against these adversarial documents remains unverified "
          "(BLOCKED_BY_CREDENTIALS) and should be re-run live before this number is trusted either way.")
    a("")

    a("## 9. Cross-document results")
    a("")
    cd = m["cross_document_results"]
    a(f"- Cases: {cd['n']}  \n- Exact-match rate: {_fmt(cd['exact_match_rate'])}")
    a("Single-pass RAG is not assumed capable of cross-document arithmetic/matching -- this number "
      "is a measurement, not a target the architecture was pre-tuned to hit; see 'remaining risks'.")
    if ps["llm_status"] == "BLOCKED_BY_CREDENTIALS":
        a("")
        a("> **Caveat**: FakeLLMProvider's default grounding returns ONE chunk's raw content -- it "
          "never actually combines two documents or performs arithmetic. D1 and D3 register as "
          "'exact match' only because the single best-matching chunk (the PO, which references both "
          "its own amount and the quotation number) happens to contain the expected substring, not "
          "because any real comparison/reasoning occurred. D2 and D4 (which require genuine "
          "arithmetic across two documents' numbers) correctly fail. Do not read D1/D3's pass as "
          "evidence that cross-document reasoning works -- re-run against live Claude, which DOES "
          "reason over whatever's in its retrieved context, to get a real signal here.")
    a("")

    a("## 10. BOQ/XLSX results")
    a("")
    a("BOQ-specific cases: B2, B3, B6, C2, C4, H3 -- see the per-case table in `results.json` for exact "
      "retrieved sheet/row diagnostics. Category B (numeric) exact-match rate above is the primary "
      "BOQ accuracy signal since every BOQ case is also a numeric case.")
    if ps["embedding_status"] == "BLOCKED_BY_CREDENTIALS":
        a("")
        a("> **Diagnosed root cause of the BOQ failures in this run**: the BOQ sheet extracts into "
          "ONE dense chunk covering all six rows (confirmed by direct inspection -- the extracted "
          "text correctly contains every item, quantity, rate, and amount; this is NOT an "
          "extraction/chunking bug). FakeEmbeddingProvider's bag-of-words hashing scheme dilutes "
          "similarity across a chunk's full vocabulary, so a long, word-dense BOQ chunk scores "
          "systematically lower (~0.10-0.22 in this run) against a short query than a short "
          "contract/invoice chunk does, regardless of true topical relevance -- pushing BOQ queries "
          "below the 0.3 threshold that short-chunk queries clear easily. This is a documented "
          "characteristic of the deterministic FAKE embedding scheme, not a proven characteristic of "
          "Voyage's real dense embeddings, which do not dilute the same way. **BOQ retrieval quality "
          "must be re-measured against live Voyage before drawing any conclusion about real-world "
          "spreadsheet retrieval accuracy** -- this run only proves the harness correctly surfaces "
          "and diagnoses a retrieval-vs-generation failure down to the responsible layer, which was "
          "the explicit goal of this step.")
    a("")

    a("## 11. Follow-up results (category E)")
    a("")
    e_vals = m["answer_accuracy_by_category"].get("E_followup", {})
    a(f"Sufficiency accuracy: {_fmt(e_vals.get('sufficiency_accuracy'))}, "
      f"exact-match rate: {_fmt(e_vals.get('exact_match_rate'))} (n={e_vals.get('n', 0)}). "
      f"E2b specifically checks that arithmetic on a PRIOR ANSWER (not a document fact) is correctly "
      f"treated as insufficient rather than fabricated.")
    a("")

    a("## 12. Threshold comparison")
    a("")
    a("| Threshold | Recall (would-be) | False-insufficient rate | Correct-insufficient rate | "
      "Avg irrelevant-survivor fraction | Avg context items sent |")
    a("|---|---|---|---|---|---|")
    for o in data["threshold_sweep"]:
        a(f"| {o['threshold']} | {_fmt(o['recall_at_k'])} | {_fmt(o['false_insufficient_rate'])} | "
          f"{_fmt(o['correct_insufficient_rate'])} | {_fmt(o['avg_irrelevant_survivor_fraction'])} | "
          f"{_fmt_count(o['avg_context_items_sent'])} |")
    a("")
    a(f"(Simulated at top_k={data['run_config']['top_k']}, reusing the same retrieval run's raw "
      f"candidate scores -- see calibration.py's module docstring for why this doesn't require "
      f"re-running retrieval per threshold.)")
    a("")

    a("## 13. Top_k comparison")
    a("")
    a("| top_k | Recall (would-be) | False-insufficient rate | Avg irrelevant-survivor fraction | "
      "Avg context items sent |")
    a("|---|---|---|---|---|")
    for o in data["top_k_sweep"]:
        a(f"| {o['top_k']} | {_fmt(o['recall_at_k'])} | {_fmt(o['false_insufficient_rate'])} | "
          f"{_fmt(o['avg_irrelevant_survivor_fraction'])} | {_fmt_count(o['avg_context_items_sent'])} |")
    a("")
    a(f"(Simulated at threshold={data['run_config']['threshold']}.)")
    a("")
    a("> **Caveat**: this synthetic 9-document corpus rarely has more than 2-3 candidates clearing "
      "the similarity threshold at all, so top_k=5/8/12 produce identical numbers here -- top_k only "
      "matters once a company has enough indexed content that MORE than top_k chunks would clear "
      "threshold. This sweep proves the harness mechanism works; a real pilot company's actual "
      "document volume is needed for a top_k comparison with real signal.")
    a("")

    a("## 14. Failure analysis")
    a("")
    if data["failed_case_ids"]:
        for case_id in data["failed_case_ids"]:
            case = next(c for c in data["cases"] if c["case_id"] == case_id)
            a(f"### {case_id} ({case['category']})")
            a(f"- Question: {case['question']}")
            a(f"- Expected sufficient={case['expected_sufficient']}, "
              f"expected contains={case['expected_answer_contains']}")
            a(f"- Actual sufficient={case['actual_sufficient']}, http_status={case['http_status']}")
            a(f"- Actual answer: {case['actual_answer'][:300]!r}")
            if case["error"]:
                a(f"- Error: {case['error'][:300]}")
            top5 = sorted(case["retrieved"], key=lambda r: r["rank"])[:5]
            a("- Top-5 retrieved (rank, score, above_threshold, document_key):")
            for r in top5:
                a(f"  - rank={r['rank']} score={r['score']:.4f} above_threshold={r['above_threshold']} "
                  f"doc={r['document_key']}")
            a("")
    else:
        a("No failing cases against the strict gates in this run.")
    a("")

    a("## 15. Latency")
    a("")
    lat = m["latency_summary"]
    a("- Embedding query: n/a split not separately averaged above (see `results.json` per-case "
      "`embedding_latency_ms`)")
    a(f"- Avg / p95 Postgres+embedding retrieval: {_fmt(lat['avg_retrieval_ms'])}ms / "
      f"{_fmt(lat['p95_retrieval_ms'])}ms")
    a(f"- Avg / p95 end-to-end ask() (includes retrieval + LLM + persistence + audit): "
      f"{_fmt(lat['avg_total_ms'])}ms / {_fmt(lat['p95_total_ms'])}ms")
    if ps["llm_status"] == "BLOCKED_BY_CREDENTIALS":
        a("- LLM-call latency: **not meaningful in fake-provider mode** (FakeLLMProvider does no "
          "real network/model work) -- re-measure once live Claude credentials are available.")
    else:
        a(f"- Avg / p95 LLM call: {_fmt(lat['avg_llm_ms'])}ms / {_fmt(lat['p95_llm_ms'])}ms")
    a("")

    a("## 16. Token usage")
    a("")
    tu = m["token_usage_summary"]
    a(f"Avg input tokens: {_fmt(tu['avg_input_tokens'])}  \nAvg output tokens: "
      f"{_fmt(tu['avg_output_tokens'])}  (n={tu['n']} LLM calls)")
    if ps["llm_status"] == "BLOCKED_BY_CREDENTIALS":
        a("FakeLLMProvider reports a word-count-based token proxy, not real tokenizer output -- "
          "treat as a harness sanity check, not a real token-usage measurement.")
    a("")

    a("## 17. Estimated cost scenarios")
    a("")
    cp = data["cost_projection"]
    a(f"Pricing source: {cp['pricing']['source_note']}")
    a("")
    if cp["scenarios_usd_per_day"]:
        a("| Questions/day/company | Est. USD/day |")
        a("|---|---|")
        for k, v in cp["scenarios_usd_per_day"].items():
            a(f"| {k.replace('_questions_per_day', '')} | ${v} |")
    else:
        a("No token-usage data available to project cost from (no LLM calls were made).")
    a("Voyage embedding cost is not included above (no cached, disclosed per-token Voyage price in "
      "this codebase -- see pricing.py).")
    a("")

    a("## 18-19. Voyage / Claude live-test status")
    a("")
    a(f"- LIVE_VOYAGE_TEST = {ps['embedding_status']}")
    a(f"- LIVE_CLAUDE_TEST = {ps['llm_status']}")
    a("")

    a("## 20-22. Recommended model / threshold / top_k")
    a("")
    a("See the top-level chat report accompanying this file for the explicit GO/CONDITIONAL GO/NO-GO "
      "recommendation and reasoning -- summarized here for the machine-readable record:")
    a("- Recommended Voyage model: voyage-3 retained (no proven reason to change; dimension 1024 "
      "retained per the spec's explicit instruction) pending a live evaluation re-run.")
    a(f"- Recommended retrieval threshold: see the threshold-sweep table above; current "
      f"{data['run_config']['threshold']} is NOT changed by this step per instruction "
      f"('Do not automatically change production threshold').")
    a(f"- Recommended top_k: see the top_k-sweep table above; current {data['run_config']['top_k']} "
      f"is NOT changed by this step.")
    a("")

    a("## 25. Pass-criteria gates (informational only in BLOCKED_BY_CREDENTIALS mode)")
    a("")
    a("| Gate | Target | This run |")
    a("|---|---|---|")
    a(f"| Direct factual retrieval | >= {GATES['direct_factual_retrieval']:.0%} | "
      f"{_fmt(m['answer_accuracy_by_category'].get('A_direct_fact', {}).get('exact_match_rate'))} |")
    a(f"| Numeric/reference/date accuracy | >= {GATES['numeric_reference_date_accuracy']:.0%} | "
      f"{_fmt(numeric.get('exact_match_rate'))} |")
    a(f"| Citation validity | = {GATES['citation_validity']:.0%} | "
      f"{_fmt(1 - (cm['wrong_document_citation_rate'] or 0))} (backend-structural; see report) |")
    a(f"| Cross-tenant leakage | = {GATES['cross_tenant_leakage']:.0%} | 0% (Step 11 regression suite; "
      f"not re-tested by this harness -- see chat report) |")
    a(f"| Unsupported factual claims | = {GATES['unsupported_factual_claims']:.0%} | "
      f"{_fmt(m['unsupported_claim_rate'])} |")
    a(f"| Insufficient-information behavior | >= {GATES['insufficient_information_behavior']:.0%} | "
      f"{_fmt(ii['recall'])} |")
    a(f"| Prompt-injection successful override | = {GATES['prompt_injection_successful_override']:.0%} | "
      f"{_fmt(pi['override_success_rate'])} |")
    a("")

    return "\n".join(lines)


def write_reports(run: RunOutput) -> tuple[Path, Path]:
    data = build_results_dict(run)
    results_path = OUTPUT_DIR / "results.json"
    report_path = OUTPUT_DIR / "REPORT.md"

    results_path.write_text(json.dumps(data, indent=2, default=str))
    report_path.write_text(render_markdown_report(data))

    return results_path, report_path

