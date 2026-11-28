"""
Operational ML commands.

    python -m app.ml.cli backfill-embeddings [--type property|profile|all]
    python -m app.ml.cli train-ranker [--dry-run] [--min-rows N]
    python -m app.ml.cli train-listing-ranker [--dry-run] [--min-rows N]
    python -m app.ml.cli evaluate-moderation [--llm] [--file PATH]

`train-ranker` also runs weekly in Celery beat (task `ml.train_ranker`). `evaluate-moderation
--llm` calls the Claude API once per example in the eval file (costs money; needs a key).
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import List

from app.ml.evaluation import classification_report
from app.ml.moderation import decide, prescreen

DEFAULT_EVAL = Path(__file__).parent / "data" / "moderation_eval.jsonl"


async def _backfill(entity: str) -> None:
    from app.core.database import AsyncSessionLocal
    from app.ml.embeddings import get_embedder
    from app.ml.indexing import backfill

    for entity_type in (["property", "profile"] if entity == "all" else [entity]):
        embedder = get_embedder(entity_type)
        async with AsyncSessionLocal() as db:
            result = await backfill(db, entity_type, embedder)
        print(f"{entity_type}: {result} (model {embedder.model_id})")


async def _train(dry_run: bool, min_rows: int | None, listings: bool = False) -> None:
    from app.core.database import AsyncSessionLocal
    from app.ml.training import train_listing_ranker, train_ranker

    async with AsyncSessionLocal() as db:
        run = train_listing_ranker if listings else train_ranker
        report = await run(db, dry_run=dry_run, min_rows=min_rows)
    print(json.dumps({"rows": report.rows, "activated": report.activated, "version": report.version,
                      "reason": report.reason, "metrics": report.metrics}, indent=2, default=str))


def load_eval(path: Path) -> List[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evaluate_rules(examples: List[dict]) -> dict:
    """Rule pre-screen against gold labels.

    - "flag" = sent for review (level review/high); should catch every unsafe and review example.
    - "warn" = warned immediately without AI (level high); should rarely fire on safe messages.
    """
    gold_flag = ["flag" if e["label"] != "safe" else "clear" for e in examples]
    gold_warn = ["warn" if e["label"] == "unsafe" else "none" for e in examples]
    levels = [prescreen(e["text"]).level for e in examples]
    pred_flag = ["flag" if lvl != "clear" else "clear" for lvl in levels]
    pred_warn = ["warn" if lvl == "high" else "none" for lvl in levels]
    return {
        "flag_for_review": classification_report(gold_flag, pred_flag),
        "warn_without_ai": classification_report(gold_warn, pred_warn),
        "misses": [e["text"] for e, g, p in zip(examples, gold_flag, pred_flag) if g == "flag" and p == "clear"],
        "false_alarms": [e["text"] for e, g, p in zip(examples, gold_warn, pred_warn) if g == "none" and p == "warn"],
    }


async def evaluate_with_llm(examples: List[dict]) -> dict:
    from app.ml.llm import LLMUnavailable
    from app.ml.moderation import classify_with_llm

    gold, pred, errors = [], [], 0
    for e in examples:
        pre = prescreen(e["text"])
        try:
            verdict = await classify_with_llm(e["text"], kind="message", signals=pre.signals)
        except LLMUnavailable:
            errors += 1
            verdict = None
        gold.append("warn" if e["label"] == "unsafe" else "none")
        pred.append("warn" if decide(pre, verdict).warning else "none")
    return {"warn": classification_report(gold, pred), "llm_errors": errors}


async def _evaluate(path: Path, llm: bool) -> None:
    examples = load_eval(path)
    out = {"examples": len(examples), "rules": evaluate_rules(examples)}
    if llm:
        out["rules_plus_ai"] = await evaluate_with_llm(examples)
    print(json.dumps(out, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.ml.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backfill-embeddings")
    b.add_argument("--type", choices=["property", "profile", "all"], default="all")
    t = sub.add_parser("train-ranker")
    t.add_argument("--dry-run", action="store_true")
    t.add_argument("--min-rows", type=int)
    lt = sub.add_parser("train-listing-ranker")
    lt.add_argument("--dry-run", action="store_true")
    lt.add_argument("--min-rows", type=int)
    e = sub.add_parser("evaluate-moderation")
    e.add_argument("--llm", action="store_true", help="Also run Claude on every example (paid API calls)")
    e.add_argument("--file", type=Path, default=DEFAULT_EVAL)
    args = parser.parse_args()

    if args.command == "backfill-embeddings":
        asyncio.run(_backfill(args.type))
    elif args.command == "train-ranker":
        asyncio.run(_train(args.dry_run, args.min_rows))
    elif args.command == "train-listing-ranker":
        asyncio.run(_train(args.dry_run, args.min_rows, listings=True))
    else:
        asyncio.run(_evaluate(args.file, args.llm))


if __name__ == "__main__":
    main()
