"""Run a low-cost silver-label sanity baseline using sampled HotPulse hints."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path
from typing import Any

from eval.harness import load_dataset
from eval.silver_metrics import compare_with_baseline_hints
from src.chains.l1_singleshot import run_judge
from src.common.config import get_settings
from src.common.models import JudgeRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run silver-label L1 sanity baseline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default="")
    return parser


def _default_output_path() -> Path:
    return Path("eval") / "reports" / f"{date.today().isoformat()}-sampled-v1-20-silver-baseline.md"


async def _judge_runner(sample: dict[str, Any]) -> dict[str, Any]:
    request = JudgeRequest.model_validate(
        {
            "rawDocument": sample["rawDocument"],
            "topicContext": sample["topicContext"],
        }
    )
    result = await run_judge(request)
    return result.model_dump()


def _render_report(
    *,
    model_name: str,
    dataset_path: Path,
    summary: dict[str, float | int],
) -> str:
    return f"""# Silver Baseline Report

## Metadata

- Dataset: `{dataset_path.name}`
- Model: `{model_name}`
- Label source: `baselineHints from fullstack-product hotspot_item`

## Agreement

- evaluated samples: `{summary['evaluated_samples']}`
- isReal agreement: `{summary['is_real_agreement']:.2%}` over `{summary['is_real_coverage']}` samples
- importance agreement: `{summary['importance_agreement']:.2%}` over `{summary['importance_coverage']}` samples
- keywordMentioned agreement: `{summary['keyword_mentioned_agreement']:.2%}` over `{summary['keyword_mentioned_coverage']}` samples
- relevance bucket agreement: `{summary['relevance_bucket_agreement']:.2%}` over `{summary['relevance_bucket_coverage']}` samples
- summary similarity: `{summary['summary_similarity']:.4f}` over `{summary['summary_coverage']}` samples

## Caveats

- This is a silver-label sanity report, not the final human-annotated baseline.
- `baselineHints` come from the existing HotPulse rule / legacy judgement path.
- Use this report to gauge directional agreement and engineering readiness, not final model quality.
"""


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    model_name = args.model or settings.brain_default_model
    output_path = args.output or _default_output_path()

    samples = load_dataset(args.dataset)
    results = [await _judge_runner(sample) for sample in samples]
    summary = compare_with_baseline_hints(samples, results)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        _render_report(model_name=model_name, dataset_path=args.dataset, summary=summary),
        encoding="utf-8",
    )
    print(summary)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
