"""Prompt loading helpers shared by chains and observability."""

from __future__ import annotations

from pathlib import Path


def load_markdown_prompt(prompt_path: Path, default_version: str) -> tuple[str, str]:
    text = prompt_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Prompt file {prompt_path} is missing frontmatter.")

    metadata = parts[1]
    body = parts[2].strip()
    version = default_version
    for line in metadata.splitlines():
        if line.startswith("version:"):
            version = line.split(":", 1)[1].strip()
            break
    return version, body
