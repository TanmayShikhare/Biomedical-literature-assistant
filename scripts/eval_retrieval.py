#!/usr/bin/env python3
"""
Measure whether expected PMIDs appear after retrieval (no LLM).

Copy retrieval_eval.example.json to retrieval_eval.json and edit PMIDs you care about.
Run after ingest so Chroma + BM25 exist.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.retrieval_eval import RowResult, eval_rows

JSON_HELP = "Write full metrics JSON to this file (human summary stays on stdout)."


def _format_human(results: list[RowResult]) -> tuple[str, dict]:
    n = len(results)
    ok_q = sum(1 for r in results if r.ok)
    total_need = sum(len(r.must_include) for r in results)
    total_hit = sum(len(r.hit) for r in results)
    mean_pmid_recall = sum(r.pmid_recall for r in results) / n if n else 0.0

    lines: list[str] = []
    for r in results:
        qshort = (r.question[:72] + "…") if len(r.question) > 72 else r.question
        if r.ok:
            lines.append(f"OK   [{r.pmid_recall:.0%} pmid_recall] {qshort}")
        else:
            lines.append(f"MISS [{r.pmid_recall:.0%} pmid_recall] {qshort}")
            lines.append(f"      missing {sorted(r.miss)} (required {sorted(r.must_include)})")
    summary = (
        f"\n── Summary ──\n"
        f"questions_passed: {ok_q}/{n}\n"
        f"pmid_hits / pmid_required: {total_hit}/{total_need}\n"
        f"mean_pmid_recall_per_question: {mean_pmid_recall:.4f}\n"
    )
    human = "\n".join(lines) + summary

    payload = {
        "eval_file": "",
        "questions_passed": ok_q,
        "questions_total": n,
        "question_pass_rate": ok_q / n if n else 0.0,
        "pmid_hits": total_hit,
        "pmid_required": total_need,
        "mean_pmid_recall_per_question": round(mean_pmid_recall, 6),
        "rows": [
            {
                "question": r.question,
                "must_include_pmids": sorted(r.must_include),
                "hit_pmids": sorted(r.hit),
                "miss_pmids": sorted(r.miss),
                "ok": r.ok,
                "pmid_recall": round(r.pmid_recall, 6),
            }
            for r in results
        ],
    }
    return human, payload


def main() -> None:
    p = argparse.ArgumentParser(description="Retrieval recall vs must-include PMIDs (no LLM).")
    p.add_argument(
        "--eval-file",
        type=Path,
        default=ROOT / "retrieval_eval.json",
        help="JSON array of {question, must_include_pmids}",
    )
    p.add_argument("--json-out", type=Path, default=None, help=JSON_HELP)
    p.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON to stdout (for scripts); no human summary.",
    )
    p.add_argument(
        "--min-question-pass-rate",
        type=float,
        default=None,
        help="Exit 1 if fraction of fully passing questions is below this (0–1).",
    )
    args = p.parse_args()
    path = args.eval_file
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"Create {path} (copy from retrieval_eval.example.json).", file=sys.stderr)
        sys.exit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("eval file must be a JSON array", file=sys.stderr)
        sys.exit(1)

    settings = get_settings()
    results = eval_rows(data, settings)
    if not results:
        print("No valid rows in eval file.", file=sys.stderr)
        sys.exit(1)

    human, payload = _format_human(results)
    payload["eval_file"] = str(path)

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"

    if args.json_only:
        sys.stdout.write(text)
    else:
        print(human)

    if args.json_out is not None:
        outp = args.json_out if args.json_out.is_absolute() else ROOT / args.json_out
        outp.write_text(text, encoding="utf-8")
        if not args.json_only:
            print(f"(wrote JSON metrics to {outp})", file=sys.stderr)

    if args.min_question_pass_rate is not None:
        rate = payload["question_pass_rate"]
        if rate < args.min_question_pass_rate:
            print(
                f"FAIL: question_pass_rate {rate:.4f} < {args.min_question_pass_rate}",
                file=sys.stderr,
            )
            sys.exit(1)

    ok_q = payload["questions_passed"]
    n = payload["questions_total"]
    sys.exit(0 if ok_q == n else 2)


if __name__ == "__main__":
    main()
