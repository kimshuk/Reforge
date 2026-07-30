from uuid import uuid4

import pytest

from app.database import Base
from app.errors import AppError
from app.models import CandidateClipping
from app.store import TranscriptStore


class RecordingSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit_count = 0
        self.rollback_count = 0

    def add(self, value: object) -> None:
        self.added.append(value)

    def add_all(self, values: list[object]) -> None:
        self.added.extend(values)

    async def flush(self) -> None:
        for value in self.added:
            if getattr(value, "id", None) is None:
                value.id = uuid4()

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


class FailingCommitSession(RecordingSession):
    async def commit(self) -> None:
        raise RuntimeError("database commit failed")


def clipping(run_id, title: str) -> CandidateClipping:
    return CandidateClipping(
        source_id=uuid4(),
        transcript_id=uuid4(),
        analysis_run_id=run_id,
        topic_chunk_id=uuid4(),
        kind="entity",
        title=title,
        text="Occurrence",
        brief="Brief occurrence",
        level1="Simple explanation.",
        level2="Contextual explanation. Another sentence.",
        level3="Detailed explanation. More reasoning. A final implication.",
        signal_level="high",
        source_ref_status="precise",
        source_refs=[
            {
                "startSegmentId": "seg-1",
                "endSegmentId": "seg-2",
                "timestamp": "00:46",
                "ref": "https://example.com?t=46s",
                "text": "Occurrence",
            }
        ],
    )


def test_category_tables_preserve_occurrence_membership_constraints() -> None:
    category = Base.metadata.tables["keyword_categories"]
    membership = Base.metadata.tables["keyword_category_memberships"]

    assert {"analysisRunId", "sequence", "title", "normalizedTitle"} <= set(category.c.keys())
    assert {"analysisRunId", "categoryId", "candidateClippingId", "sequence"} <= set(membership.c.keys())
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in membership.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert ("candidateClippingId",) in unique_columns
    assert ("categoryId", "sequence") in unique_columns


@pytest.mark.asyncio
async def test_saves_occurrences_categories_and_memberships_in_one_commit() -> None:
    run_id = uuid4()
    first = clipping(run_id, "Codex")
    second = clipping(run_id, "Codex")
    session = RecordingSession()

    saved_clippings, categories, memberships = await TranscriptStore(session).save_category_graph(
        run_id,
        [first, second],
        [{"title": "OpenAI", "keywordIds": ["K001", "K002"]}],
        {"K001": first, "K002": second},
    )

    assert saved_clippings == [first, second]
    assert [item.title for item in categories] == ["OpenAI"]
    assert [item.candidate_clipping_id for item in memberships] == [first.id, second.id]
    assert all(item.analysis_run_id == run_id for item in categories + memberships)
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_rejects_cross_run_occurrence_before_persistence() -> None:
    run_id = uuid4()
    wrong_run = clipping(uuid4(), "Codex")
    session = RecordingSession()

    with pytest.raises(AppError, match="analysis run"):
        await TranscriptStore(session).save_category_graph(
            run_id,
            [wrong_run],
            [{"title": "OpenAI", "keywordIds": ["K001"]}],
            {"K001": wrong_run},
        )

    assert session.commit_count == 0
    assert session.added == []


@pytest.mark.asyncio
async def test_rolls_back_the_entire_category_graph_when_commit_fails() -> None:
    run_id = uuid4()
    occurrence = clipping(run_id, "Codex")
    session = FailingCommitSession()

    with pytest.raises(RuntimeError, match="commit failed"):
        await TranscriptStore(session).save_category_graph(
            run_id,
            [occurrence],
            [{"title": "OpenAI", "keywordIds": ["K001"]}],
            {"K001": occurrence},
        )

    assert session.rollback_count == 1
