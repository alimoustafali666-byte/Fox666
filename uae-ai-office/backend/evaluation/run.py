"""Step 11.5 evaluation harness entry point.

Usage (from the backend/ directory, with a local PostgreSQL 16 server
available -- see README.md's Database setup):

    python -m evaluation.run [--keep-db]

Requires no credentials to run: with no ANTHROPIC_API_KEY /
EMBEDDING_API_KEY in the environment, it runs entirely against
Fake{Embedding,LLM}Provider and labels the run BLOCKED_BY_CREDENTIALS.
Set those two environment variables (real Voyage/Anthropic keys) before
invoking to run a live evaluation instead -- no code changes needed.

Writes evaluation/results.json and evaluation/REPORT.md.
"""

import argparse
import sys

from evaluation import (
    _bootstrap,  # noqa: F401 -- sets required env vars before any app.* import below
)
from evaluation.report import write_reports
from evaluation.runner import run_full_evaluation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Step 11.5 RAG evaluation harness.")
    parser.add_argument(
        "--keep-db", action="store_true",
        help="Do not drop the scratch evaluation database on exit (for manual inspection).",
    )
    args = parser.parse_args()

    print("[evaluation] starting run...", file=sys.stderr)
    run = run_full_evaluation(keep_db=args.keep_db)
    print(
        f"[evaluation] run complete: {len(run.case_results)} cases, "
        f"embedding={run.provider_status.embedding_status}, llm={run.provider_status.llm_status}",
        file=sys.stderr,
    )

    results_path, report_path = write_reports(run)
    print(f"[evaluation] wrote {results_path}", file=sys.stderr)
    print(f"[evaluation] wrote {report_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

