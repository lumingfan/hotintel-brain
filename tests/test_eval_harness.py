"""Eval harness smoke tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.harness import run_eval


@pytest.mark.asyncio
async def test_eval_harness_runs_with_mock_runner(tmp_path: Path) -> None:
    dataset_path = tmp_path / "labeled-v1.jsonl"
    report_path = tmp_path / "reports" / "eval-report.md"
    samples = [
        {"rawDocumentId": "rd_001", "labels": {"importance": "high"}},
        {"rawDocumentId": "rd_002", "labels": {"importance": "medium"}},
    ]
    dataset_path.write_text(
        "\n".join(json.dumps(sample, ensure_ascii=False) for sample in samples),
        encoding="utf-8",
    )

    async def mock_runner(sample: dict[str, object]) -> dict[str, object]:
        return {
            "rawDocumentId": sample["rawDocumentId"],
            "partial": False,
            "importance": "high",
        }

    summary = await run_eval(
        dataset_path=dataset_path,
        runner=mock_runner,
        report_path=report_path,
        layer="L1",
        model="gpt-4o-mini",
        prompt_version="judge-v1.0",
        dataset_version="labeled-v1",
    )

    assert summary["total_samples"] == 2
    assert summary["success_count"] == 2
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "judge-v1.0" in report_text
    assert "gpt-4o-mini" in report_text
