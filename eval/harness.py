"""Minimal V1 eval harness bootstrap."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from eval.metrics import count_successes, partial_rate

Runner = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]


def load_dataset(dataset_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def _run_one(runner: Runner, sample: dict[str, Any]) -> dict[str, Any]:
    result = runner(sample)
    if inspect.isawaitable(result):
        return await result
    return result


def _render_report(
    *,
    dataset_version: str,
    layer: str,
    model: str,
    prompt_version: str,
    total_samples: int,
    success_count: int,
    partial_rate_value: float,
) -> str:
    return f"""# Eval Report

## Metadata

- Dataset version: `{dataset_version}`
- Layer: `{layer}`
- Model: `{model}`
- Prompt version: `{prompt_version}`

## Summary

- Total samples: `{total_samples}`
- Success count: `{success_count}`
- Partial rate: `{partial_rate_value:.2%}`

## Metrics

- Placeholder: importance macro-F1
- Placeholder: isReal precision / recall
- Placeholder: summary quality

## Next

- Replace placeholders with real metric calculations.
- Wire the runner to judge/summarize chains once labeled data is ready.
"""


async def run_eval(
    *,
    dataset_path: Path,
    runner: Runner,
    report_path: Path,
    layer: str,
    model: str,
    prompt_version: str,
    dataset_version: str,
) -> dict[str, Any]:
    samples = load_dataset(dataset_path)
    results = [await _run_one(runner, sample) for sample in samples]

    summary = {
        "total_samples": len(samples),
        "success_count": count_successes(results),
        "partial_rate": partial_rate(results),
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        _render_report(
            dataset_version=dataset_version,
            layer=layer,
            model=model,
            prompt_version=prompt_version,
            total_samples=summary["total_samples"],
            success_count=summary["success_count"],
            partial_rate_value=summary["partial_rate"],
        ),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    raise SystemExit("Use `run_eval(...)` from Python for now; CLI wiring lands later.")


if __name__ == "__main__":
    main()
