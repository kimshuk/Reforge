import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import errors

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration checks",
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(command: str, revision: str) -> None:
    environment = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL or ""}
    subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
    )


def connect() -> psycopg.Connection:
    assert TEST_DATABASE_URL
    return psycopg.connect(TEST_DATABASE_URL.replace("+psycopg", ""), autocommit=True)


def test_migration_and_category_membership_contract() -> None:
    run_alembic("upgrade", "head")
    with connect() as connection:
        tables = connection.execute(
            "SELECT to_regclass('keyword_categories'), "
            "to_regclass('keyword_category_memberships')"
        ).fetchone()
        assert tables == ("keyword_categories", "keyword_category_memberships")

    run_alembic("downgrade", "0001")
    try:
        with connect() as connection:
            tables = connection.execute(
                "SELECT to_regclass('keyword_categories'), "
                "to_regclass('keyword_category_memberships')"
            ).fetchone()
            assert tables == (None, None)
    finally:
        run_alembic("upgrade", "head")

    source_id, transcript_id = uuid4(), uuid4()
    run_ids = [uuid4(), uuid4()]
    chunk_ids = [uuid4(), uuid4()]
    clipping_ids = [uuid4(), uuid4()]
    category_ids = [uuid4(), uuid4()]

    with connect() as connection:
        try:
            connection.execute(
                'INSERT INTO sources (id, type, provider, "externalId") '
                "VALUES (%s, 'youtube', 'youtube', %s)",
                (source_id, f"integration-{source_id}"),
            )
            connection.execute(
                'INSERT INTO transcripts (id, "sourceId", "transcriptHash", "transcriptText") '
                "VALUES (%s, %s, %s, 'transcript')",
                (transcript_id, source_id, f"hash-{transcript_id}"),
            )
            for index in range(2):
                connection.execute(
                    'INSERT INTO analysis_runs (id, "sourceType", "sourceId", '
                    '"transcriptId", status, provider, model, "promptVersion", '
                    '"schemaVersion", temperature) VALUES '
                    "(%s, 'youtube', %s, %s, 'running', 'openai', 'test', 'v2', 'v2', 0.2)",
                    (run_ids[index], source_id, transcript_id),
                )
                connection.execute(
                    'INSERT INTO topic_chunks (id, "sourceId", "transcriptId", '
                    '"analysisRunId", sequence, "startSegmentId", "endSegmentId", '
                    '"startTime", "endTime", title, summary, "signalLevel", '
                    '"coverageStatus", text) VALUES '
                    "(%s, %s, %s, %s, 0, %s, %s, 0, 1, 'topic', 'summary', "
                    "'high', 'covered', 'text')",
                    (
                        chunk_ids[index],
                        source_id,
                        transcript_id,
                        run_ids[index],
                        f"s{index}",
                        f"s{index}",
                    ),
                )
                connection.execute(
                    'INSERT INTO candidate_clippings (id, "sourceId", "transcriptId", '
                    '"analysisRunId", "topicChunkId", kind, title, text, brief, '
                    'level1, level2, level3, "signalLevel", "sourceRefStatus", '
                    '"sourceRefs") VALUES (%s, %s, %s, %s, %s, '
                    "'claim', 'Codex', 'text', 'brief', 'l1', 'l2', 'l3', "
                    "'high', 'resolved', '[]')",
                    (
                        clipping_ids[index],
                        source_id,
                        transcript_id,
                        run_ids[index],
                        chunk_ids[index],
                    ),
                )
                connection.execute(
                    'INSERT INTO keyword_categories '
                    '(id, "analysisRunId", sequence, title, "normalizedTitle") '
                    "VALUES (%s, %s, 0, %s, %s)",
                    (
                        category_ids[index],
                        run_ids[index],
                        f"Category {index}",
                        f"category {index}",
                    ),
                )

            connection.execute(
                'INSERT INTO keyword_category_memberships '
                '(id, "analysisRunId", "categoryId", "candidateClippingId", sequence) '
                "VALUES (%s, %s, %s, %s, 0)",
                (uuid4(), run_ids[0], category_ids[0], clipping_ids[0]),
            )

            with pytest.raises(errors.RaiseException):
                connection.execute(
                    'INSERT INTO keyword_category_memberships '
                    '(id, "analysisRunId", "categoryId", "candidateClippingId", sequence) '
                    "VALUES (%s, %s, %s, %s, 1)",
                    (uuid4(), run_ids[0], category_ids[1], clipping_ids[1]),
                )
            with pytest.raises(errors.UniqueViolation):
                connection.execute(
                    'INSERT INTO keyword_category_memberships '
                    '(id, "analysisRunId", "categoryId", "candidateClippingId", sequence) '
                    "VALUES (%s, %s, %s, %s, 1)",
                    (uuid4(), run_ids[0], category_ids[0], clipping_ids[0]),
                )

            connection.execute("DELETE FROM analysis_runs WHERE id = %s", (run_ids[0],))
            assert connection.execute(
                'SELECT count(*) FROM keyword_categories WHERE "analysisRunId" = %s',
                (run_ids[0],),
            ).fetchone()[0] == 0
            assert connection.execute(
                'SELECT count(*) FROM keyword_category_memberships '
                'WHERE "analysisRunId" = %s',
                (run_ids[0],),
            ).fetchone()[0] == 0
        finally:
            connection.execute("DELETE FROM sources WHERE id = %s", (source_id,))
