"""Bootstrap CLI for sampling labeled data from HotPulse sources."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sample raw_document rows from HotPulse and write JSONL output.",
    )
    parser.add_argument("--dsn", default=os.getenv("HOTPULSE_DB_DSN", ""))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--days", type=int, default=30)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.dsn:
        raise SystemExit(
            "Missing HotPulse DB connection info. Pass --dsn or set HOTPULSE_DB_DSN."
        )

    raise SystemExit(
        "Sampling is not implemented yet. Expected output: JSONL rows aligned with "
        "`docs/eval/protocol.md` and `docs/data/labeling-guide.md`."
    )


if __name__ == "__main__":
    main()
