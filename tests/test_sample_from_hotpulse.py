"""Sampling script tests."""

from __future__ import annotations

from pathlib import Path

from scripts.sample_from_hotpulse import (
    build_sample_record,
    parse_jdbc_mysql_dsn,
    resolve_db_config,
    stratified_sample,
)


def test_parse_jdbc_mysql_dsn() -> None:
    host, port, database, params = parse_jdbc_mysql_dsn(
        "jdbc:mysql://localhost:3306/hot_intel?useSSL=false&serverTimezone=UTC"
    )

    assert host == "localhost"
    assert port == 3306
    assert database == "hot_intel"
    assert params["useSSL"] == "false"


def test_resolve_db_config_from_backend_env(tmp_path: Path) -> None:
    env_path = tmp_path / ".env.local"
    env_path.write_text(
        "\n".join(
            [
                "DB_URL=jdbc:mysql://localhost:3306/hot_intel?useSSL=false",
                "DB_USERNAME=hot_intel",
                "DB_PASSWORD=hot_intel",
            ]
        ),
        encoding="utf-8",
    )

    config = resolve_db_config(
        dsn="",
        db_user="",
        db_password="",
        backend_env_path=env_path,
    )

    assert config.host == "localhost"
    assert config.port == 3306
    assert config.database == "hot_intel"
    assert config.username == "hot_intel"
    assert config.password == "hot_intel"
    assert config.source == str(env_path)


def test_build_sample_record_shapes_output() -> None:
    row = {
        "raw_document_id": "rd_001",
        "title": "Anthropic releases Claude Sonnet 4.6",
        "content": "Anthropic announced Claude Sonnet 4.6.",
        "source_code": "hackernews",
        "source_url": "https://example.com",
        "author_name": "anthropic",
        "published_at": None,
        "collected_at": None,
        "topic_id": "tp_001",
        "topic_name": "AI Coding Models",
        "primary_keyword": "Claude Sonnet 4.6",
        "expanded_keywords": "Claude Sonnet||Claude Code",
        "min_relevance_score": 60,
        "require_direct_keyword_mention": 0,
    }

    record = build_sample_record(row)

    assert record["rawDocumentId"] == "rd_001"
    assert record["topicContext"]["primaryKeyword"] == "Claude Sonnet 4.6"
    assert record["topicContext"]["expandedKeywords"] == [
        "Claude Sonnet 4.6",
        "Claude Sonnet",
        "Claude Code",
    ]
    assert record["labels"]["importance"] is None


def test_stratified_sample_prefers_source_targets() -> None:
    rows = []
    for idx in range(40):
        rows.append(
            {
                "raw_document_id": f"rd_hn_{idx}",
                "title": "HN title",
                "content": "c",
                "source_code": "hackernews",
                "source_url": f"https://hn/{idx}",
                "author_name": None,
                "published_at": None,
                "collected_at": None,
                "topic_id": "tp_001",
                "topic_name": "AI",
                "primary_keyword": "AI",
                "expanded_keywords": "AI",
                "min_relevance_score": 60,
                "require_direct_keyword_mention": 0,
            }
        )
    for idx in range(40):
        rows.append(
            {
                "raw_document_id": f"rd_wb_{idx}",
                "title": "WB title",
                "content": "c",
                "source_code": "weibo",
                "source_url": f"https://wb/{idx}",
                "author_name": None,
                "published_at": None,
                "collected_at": None,
                "topic_id": "tp_001",
                "topic_name": "AI",
                "primary_keyword": "AI",
                "expanded_keywords": "AI",
                "min_relevance_score": 60,
                "require_direct_keyword_mention": 0,
            }
        )

    sampled = stratified_sample(rows, limit=20, seed=42, per_source=True)

    assert len(sampled) == 20
    sources = {record["samplingMetadata"]["sourceCode"] for record in sampled}
    assert "hackernews" in sources
    assert "weibo" in sources
