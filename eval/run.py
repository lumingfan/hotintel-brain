"""CLI entrypoint for the minimal V1 judge baseline runner."""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from pathlib import Path
from typing import Any

from eval.harness import run_eval
from src.chains.l1_singleshot import run_judge
from src.common.config import get_settings
from src.common.models import JudgeRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the minimal L1 eval harness.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--layer", default="L1")
    parser.add_argument("--model", default="")
    parser.add_argument("--prompt-version", default="judge-v1.0")
    parser.add_argument("--dataset-version", default="sampled-v1")
    return parser


def _default_output_path(dataset_version: str) -> Path:
    return Path("eval") / "reports" / f"{date.today().isoformat()}-{dataset_version}-l1-baseline.md"


async def _judge_runner(sample: dict[str, Any]) -> dict[str, Any]:
    request = JudgeRequest.model_validate(
        {
            "rawDocument": sample["rawDocument"],
            "topicContext": sample["topicContext"],
        }
    )
    result = await run_judge(request)
    return result.model_dump()


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = get_settings()
    output_path = args.output or _default_output_path(args.dataset_version)
    model_name = args.model or settings.brain_default_model

    summary = await run_eval(
        dataset_path=args.dataset,
        runner=_judge_runner,
        report_path=output_path,
        layer=args.layer,
        model=model_name,
        prompt_version=args.prompt_version,
        dataset_version=args.dataset_version,
    )
    print(summary)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
