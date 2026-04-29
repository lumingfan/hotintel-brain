"""Sample candidate L1 labeling records from the HotPulse main-project database."""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

import pymysql

FULLSTACK_PRODUCT_ROOT = Path(
    "/Users/lumingfan/postgraduate/tasks/vibe-coding/internship-portfolio/fullstack-product"
)
DEFAULT_BACKEND_ENV_PATH = FULLSTACK_PRODUCT_ROOT / "backend" / ".env.local"
FALLBACK_BACKEND_ENV_PATH = FULLSTACK_PRODUCT_ROOT / "backend" / ".env.example"
DEFAULT_OUTPUT_PATH = Path("data") / "sampled-v1-20.jsonl"
SOURCE_TARGETS = {
    "hackernews": 35,
    "bilibili": 35,
    "bing": 30,
    "sogou": 30,
    "weibo": 35,
    "twitter": 35,
}


@dataclass(frozen=True)
class DbConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    params: dict[str, str]
    source: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sample raw_document rows from HotPulse and write JSONL output.",
    )
    parser.add_argument("--dsn", default=os.getenv("HOTPULSE_DB_DSN", ""))
    parser.add_argument("--db-user", default=os.getenv("HOTPULSE_DB_USER", ""))
    parser.add_argument("--db-password", default=os.getenv("HOTPULSE_DB_PASSWORD", ""))
    parser.add_argument(
        "--backend-env",
        type=Path,
        default=DEFAULT_BACKEND_ENV_PATH,
        help="Path to fullstack-product backend .env file for local DB defaults.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-source", action="store_true")
    return parser


def parse_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_jdbc_mysql_dsn(dsn: str) -> tuple[str, int, str, dict[str, str]]:
    normalized = dsn.removeprefix("jdbc:")
    parsed = urlparse(normalized)
    if parsed.scheme != "mysql":
        raise ValueError(f"Unsupported DSN scheme for {dsn!r}; expected jdbc:mysql://...")
    database = parsed.path.lstrip("/")
    if not database:
        raise ValueError(f"Database name is missing from {dsn!r}.")
    return parsed.hostname or "localhost", parsed.port or 3306, database, dict(parse_qsl(parsed.query))


def resolve_db_config(
    *,
    dsn: str,
    db_user: str,
    db_password: str,
    backend_env_path: Path,
) -> DbConfig:
    effective_dsn = dsn
    effective_user = db_user
    effective_password = db_password
    source = "args/env"

    env_values = parse_env_file(backend_env_path)
    if not env_values and backend_env_path == DEFAULT_BACKEND_ENV_PATH:
        env_values = parse_env_file(FALLBACK_BACKEND_ENV_PATH)
        if env_values:
            backend_env_path = FALLBACK_BACKEND_ENV_PATH

    if not effective_dsn and env_values.get("DB_URL"):
        effective_dsn = env_values["DB_URL"]
        effective_user = effective_user or env_values.get("DB_USERNAME", "")
        effective_password = effective_password or env_values.get("DB_PASSWORD", "")
        source = str(backend_env_path)

    if not effective_dsn:
        raise ValueError(
            "Missing HotPulse DB connection info. Pass --dsn / --db-user / --db-password, "
            "set HOTPULSE_DB_* env vars, or provide a readable backend/.env.local."
        )
    if not effective_user:
        raise ValueError("Missing HotPulse DB username.")

    host, port, database, params = parse_jdbc_mysql_dsn(effective_dsn)
    return DbConfig(
        host=host,
        port=port,
        database=database,
        username=effective_user,
        password=effective_password,
        params=params,
        source=source,
    )


def fetch_candidate_rows(config: DbConfig, *, days: int) -> list[dict[str, Any]]:
    query = """
        SELECT
            rd.id AS raw_document_id,
            rd.title,
            rd.content,
            rd.source_code,
            rd.source_url,
            rd.author_name,
            rd.published_at,
            rd.collected_at,
            t.id AS topic_id,
            t.name AS topic_name,
            hi.is_real,
            hi.relevance_score,
            hi.relevance_reason,
            hi.keyword_mentioned,
            hi.importance_level,
            hi.summary AS hotspot_summary,
            COALESCE(
                MAX(CASE WHEN tk.keyword_type = 'PRIMARY' THEN tk.keyword_text END),
                SUBSTRING_INDEX(GROUP_CONCAT(tk.keyword_text ORDER BY tk.sort_order SEPARATOR '||'), '||', 1),
                t.name
            ) AS primary_keyword,
            GROUP_CONCAT(tk.keyword_text ORDER BY tk.sort_order SEPARATOR '||') AS expanded_keywords,
            COALESCE(MAX(tr.min_relevance_score), 60) AS min_relevance_score,
            COALESCE(MAX(tr.require_direct_keyword_mention), 0) AS require_direct_keyword_mention
        FROM raw_document rd
        JOIN scan_task st
          ON st.id = rd.scan_task_id
        JOIN topic t
          ON t.id = st.topic_id
        LEFT JOIN hotspot_item hi
          ON hi.raw_document_id = rd.id
         AND hi.topic_id = t.id
        LEFT JOIN topic_rule tr
          ON tr.topic_id = t.id
        LEFT JOIN topic_keyword tk
          ON tk.topic_id = t.id
         AND tk.is_active = TRUE
        WHERE COALESCE(rd.published_at, rd.collected_at) >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s DAY)
        GROUP BY
            rd.id,
            rd.title,
            rd.content,
            rd.source_code,
            rd.source_url,
            rd.author_name,
            rd.published_at,
            rd.collected_at,
            t.id,
            t.name
        ORDER BY COALESCE(rd.published_at, rd.collected_at) DESC
    """

    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.username,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (days,))
            return list(cursor.fetchall())
    finally:
        connection.close()


def _split_keywords(raw_keywords: str | None, primary_keyword: str) -> list[str]:
    keywords = [item.strip() for item in (raw_keywords or "").split("||") if item.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in [primary_keyword, *keywords]:
        if keyword and keyword not in seen:
            deduped.append(keyword)
            seen.add(keyword)
    return deduped


def build_sample_record(row: dict[str, Any]) -> dict[str, Any]:
    primary_keyword = row["primary_keyword"] or row["topic_name"]
    expanded_keywords = _split_keywords(row.get("expanded_keywords"), primary_keyword)

    return {
        "rawDocumentId": row["raw_document_id"],
        "rawDocument": {
            "id": row["raw_document_id"],
            "title": row["title"],
            "content": row.get("content") or "",
            "source": row["source_code"],
            "publishedAt": row["published_at"].isoformat() if row.get("published_at") else None,
            "author": row.get("author_name"),
            "url": row["source_url"],
        },
        "topicContext": {
            "topicId": row["topic_id"],
            "topicName": row["topic_name"],
            "primaryKeyword": primary_keyword,
            "expandedKeywords": expanded_keywords,
            "rule": {
                "minRelevanceScore": int(row["min_relevance_score"]),
                "requireDirectKeywordMention": bool(row["require_direct_keyword_mention"]),
            },
        },
        "labels": {
            "isReal": None,
            "importance": None,
            "summary": "",
            "summaryKeyPoints": [],
            "keywordMentioned": None,
            "relevanceBucket": None,
        },
        "labelerNotes": "",
        "baselineHints": {
            "isReal": row.get("is_real"),
            "importance": row.get("importance_level"),
            "summary": row.get("hotspot_summary") or "",
            "keywordMentioned": row.get("keyword_mentioned"),
            "relevanceScore": row.get("relevance_score"),
            "relevanceReason": row.get("relevance_reason"),
        },
        "samplingMetadata": {
            "sourceCode": row["source_code"],
            "collectedAt": row["collected_at"].isoformat() if row.get("collected_at") else None,
        },
    }


def stratified_sample(
    rows: list[dict[str, Any]],
    *,
    limit: int,
    seed: int,
    per_source: bool,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_source[row["source_code"]].append(row)

    for source_rows in by_source.values():
        rng.shuffle(source_rows)

    selected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    if per_source:
        source_counts = {source_code: 0 for source_code in SOURCE_TARGETS}
        active_sources = [source_code for source_code in SOURCE_TARGETS if by_source.get(source_code)]

        while len(selected) < limit and active_sources:
            progress = False
            for source_code in list(active_sources):
                if source_counts[source_code] >= SOURCE_TARGETS[source_code]:
                    active_sources.remove(source_code)
                    continue

                pool = by_source.get(source_code, [])
                while pool and pool[-1]["raw_document_id"] in seen_ids:
                    pool.pop()

                if not pool:
                    active_sources.remove(source_code)
                    continue

                row = pool.pop()
                selected.append(build_sample_record(row))
                seen_ids.add(row["raw_document_id"])
                source_counts[source_code] += 1
                progress = True

                if len(selected) >= limit:
                    break

            if not progress:
                break

    if len(selected) < limit:
        remaining = [row for row in rows if row["raw_document_id"] not in seen_ids]
        rng.shuffle(remaining)
        for row in remaining:
            if len(selected) >= limit:
                break
            selected.append(build_sample_record(row))
            seen_ids.add(row["raw_document_id"])

    return selected[:limit]


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = resolve_db_config(
        dsn=args.dsn,
        db_user=args.db_user,
        db_password=args.db_password,
        backend_env_path=args.backend_env,
    )
    rows = fetch_candidate_rows(config, days=args.days)
    sampled = stratified_sample(
        rows,
        limit=args.limit,
        seed=args.seed,
        per_source=args.per_source,
    )
    write_jsonl(sampled, args.output)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "records": len(sampled),
                "db_source": config.source,
                "sources": sorted({record["samplingMetadata"]["sourceCode"] for record in sampled}),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
