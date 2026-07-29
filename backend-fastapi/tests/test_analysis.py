from uuid import UUID, uuid4

import pytest

from app.analysis import (
    AnalyzeService,
    build_grouping_occurrences,
    build_topic_chunks,
    candidate_entity,
    deduplicate_occurrences,
    eligible_topic_chunks,
    resolve_boundary_labels,
)
from app.config import Settings
from app.errors import AppError
from app.models import (
    AnalysisRun,
    CandidateClipping,
    KeywordCategory,
    TopicChunk,
    TranscriptSegment,
)
from app.schemas import AnalyzeSource
from app.store import StoredTranscript


def segment(sequence: int) -> TranscriptSegment:
    return TranscriptSegment(
        id=f"hash-{sequence}",
        source_id=uuid4(),
        transcript_id=uuid4(),
        sequence=sequence,
        start_time=sequence * 20,
        end_time=(sequence + 1) * 20,
        raw_text=f"Raw {sequence}",
        text=f"Text {sequence}",
    )


def test_resolves_labels_and_repairs_reversed_boundary() -> None:
    segments = [segment(0), segment(1)]
    boundaries = resolve_boundary_labels(
        [
            {
                "startSegmentId": "S002",
                "endSegmentId": "S001",
                "title": "A topic",
                "summary": "A grounded summary",
                "signalLevel": "high",
            }
        ],
        segments,
    )

    chunks, warnings = build_topic_chunks(
        boundaries, segments, uuid4(), uuid4(), uuid4()
    )

    assert chunks[0].start_segment_id == "hash-0"
    assert chunks[0].end_segment_id == "hash-1"
    assert warnings[0].reason == "reversed_topic_chunk_repaired"


def topic_chunk(signal_level: str, start: TranscriptSegment, end: TranscriptSegment) -> TopicChunk:
    return TopicChunk(
        id=uuid4(),
        source_id=start.source_id,
        transcript_id=start.transcript_id,
        analysis_run_id=uuid4(),
        sequence=0,
        start_segment_id=start.id,
        end_segment_id=end.id,
        start_time=start.start_time,
        end_time=end.end_time,
        title="AI tools",
        summary="The speaker discusses AI tools.",
        signal_level=signal_level,
        coverage_status="pending",
        text="Transcript chunk",
    )


def candidate(start_id: str, end_id: str, title: str = "Codex") -> dict:
    return {
        "kind": "entity",
        "title": title,
        "text": "Occurrence text",
        "brief": "Autonomous coding tool introduced here",
        "simpleExplanation": "Codex is a tool that performs coding tasks.",
        "contextualExplanation": "The speaker introduces Codex as an autonomous coding tool. They describe the work it can perform.",
        "detailedExplanation": "The speaker introduces Codex as an autonomous coding tool. They claim it can perform concrete coding work. The mechanism is autonomous task execution. The example establishes why the tool matters in this section.",
        "signalLevel": "high",
        "sourceRefs": [
            {
                "startSegmentId": start_id,
                "endSegmentId": end_id,
                "timestamp": "99:99",
                "text": "Hallucinated model excerpt",
            }
        ],
    }


def clipping(start_id: str, end_id: str, *, title: str = "Codex", level2: str = "Context") -> CandidateClipping:
    return CandidateClipping(
        id=uuid4(),
        source_id=uuid4(),
        transcript_id=uuid4(),
        analysis_run_id=uuid4(),
        topic_chunk_id=uuid4(),
        kind="entity",
        title=title,
        text="Occurrence text",
        brief="Brief occurrence",
        level1="Simple definition.",
        level2=level2,
        level3="Detailed occurrence explanation.",
        signal_level="high",
        source_ref_status="precise",
        source_refs=[
            {
                "startSegmentId": start_id,
                "endSegmentId": end_id,
                "timestamp": "00:46",
                "ref": "https://example.com?t=46s",
                "text": "Grounded text",
            }
        ],
    )


def test_eligible_topic_chunks_include_high_and_medium_only() -> None:
    segments = [segment(0), segment(1)]
    chunks = [
        topic_chunk("high", *segments),
        topic_chunk("medium", *segments),
        topic_chunk("low", *segments),
        topic_chunk("off_topic", *segments),
    ]

    assert [item.signal_level for item in eligible_topic_chunks(chunks)] == ["high", "medium"]


def test_candidate_entity_builds_manual_excerpt_from_resolved_segments() -> None:
    segments = [segment(0), segment(1)]
    chunk = topic_chunk("high", *segments)

    result = candidate_entity(
        candidate(segments[0].id, segments[1].id),
        chunk,
        {item.id: item for item in segments},
        AnalyzeSource(type="manual", text="manual", target_language="en"),
        uuid4(),
        uuid4(),
        uuid4(),
    )

    assert result.source_refs[0]["text"] == "Text 0 Text 1"
    assert result.source_refs[0]["ref"] == "Text 0 Text 1"
    assert result.source_refs[0]["timestamp"] == "00:00"


def test_candidate_entity_rejects_unresolved_source_instead_of_using_chunk_start() -> None:
    segments = [segment(0), segment(1)]
    chunk = topic_chunk("high", *segments)

    with pytest.raises(AppError) as raised:
        candidate_entity(
            candidate("missing", segments[1].id),
            chunk,
            {item.id: item for item in segments},
            AnalyzeSource(type="youtube", youtube_url="https://youtube.com/watch?v=test", target_language="en"),
            uuid4(),
            uuid4(),
            uuid4(),
        )

    assert raised.value.code == "LLM_CLIPPINGS_INVALID_SOURCE_REF"


def test_deduplicates_only_same_normalized_term_and_resolved_range() -> None:
    first = clipping("seg-1", "seg-2", title="Codex", level2="First context")
    accidental_duplicate = clipping("seg-1", "seg-2", title=" codex ", level2="Duplicate context")
    later_occurrence = clipping("seg-8", "seg-9", title="Codex", level2="Competitive risk context")

    result = deduplicate_occurrences([first, accidental_duplicate, later_occurrence])

    assert result == [first, later_occurrence]
    assert result[0].level2 == "First context"
    assert result[1].level2 == "Competitive risk context"


def test_grouping_occurrences_give_equal_terms_distinct_ids() -> None:
    first = clipping("seg-1", "seg-2", level2="Autonomous tool context")
    second = clipping("seg-8", "seg-9", level2="Competitive risk context")

    metadata, by_id = build_grouping_occurrences([first, second])

    assert [item["keywordId"] for item in metadata] == ["K001", "K002"]
    assert [item["term"] for item in metadata] == ["Codex", "Codex"]
    assert metadata[0]["contextualExplanation"] == "Autonomous tool context"
    assert metadata[1]["contextualExplanation"] == "Competitive risk context"
    assert by_id == {"K001": first, "K002": second}


class ServiceStore:
    def __init__(self, segments: list[TranscriptSegment]) -> None:
        self.segments = segments
        self.run = AnalysisRun(
            id=uuid4(),
            source_type="youtube",
            status="running",
            provider="openai",
            model="test",
            prompt_version="test",
            schema_version="test",
            temperature=0.2,
        )
        self.saved_clippings: list[CandidateClipping] = []
        self.completed = False
        self.db = self

    async def create_analysis_run(self, _source_type: str, _llm: dict) -> AnalysisRun:
        return self.run

    async def set_transcript(self, **_kwargs) -> StoredTranscript:
        return StoredTranscript(self.segments[0].source_id, self.segments[0].transcript_id, "hash")

    async def mark_transcript(self, _run: AnalysisRun, _stored: StoredTranscript) -> None:
        pass

    async def list_segments(self, _transcript_id: UUID) -> list[TranscriptSegment]:
        return self.segments

    async def save_chunks(self, chunks: list[TopicChunk]) -> list[TopicChunk]:
        for chunk in chunks:
            chunk.id = chunk.id or uuid4()
        return chunks

    async def save_warnings(self, _warnings: list) -> None:
        pass

    async def save_category_graph(self, run_id, clippings, grouping, occurrences_by_id):
        self.saved_clippings = clippings
        for clipping_item in clippings:
            clipping_item.id = clipping_item.id or uuid4()
        categories = [
            KeywordCategory(
                id=uuid4(),
                analysis_run_id=run_id,
                sequence=index,
                title=item["title"],
                normalized_title=item["title"].casefold(),
            )
            for index, item in enumerate(grouping)
        ]
        return clippings, categories, []

    async def commit(self) -> None:
        pass

    async def mark_completed(self, _run: AnalysisRun) -> None:
        self.completed = True

    async def mark_failed(self, *_args) -> None:
        raise AssertionError("analysis should not fail")


class ServiceLlm:
    def __init__(self) -> None:
        self.extracted_titles: list[str] = []
        self.grouping_input: list[dict] = []

    async def generate_topic_chunks(self, _segments, _language, _options):
        return [
            {"startSegmentId": "S001", "endSegmentId": "S002", "title": "Introduction", "summary": "Codex is introduced.", "signalLevel": "high"},
            {"startSegmentId": "S003", "endSegmentId": "S005", "title": "Competitive risk", "summary": "Codex threatens software companies.", "signalLevel": "medium"},
            {"startSegmentId": "S006", "endSegmentId": "S006", "title": "Outro", "summary": "Closing remarks.", "signalLevel": "low"},
        ]

    async def generate_candidate_clippings(self, title, _summary, _segments, _language, _options):
        self.extracted_titles.append(title)
        if title == "Introduction":
            occurrence = candidate("S002", "S002")
            return [occurrence, {**occurrence}]
        risk = candidate("S004", "S005")
        risk["brief"] = "Competitive risk to software companies"
        risk["contextualExplanation"] = "The speaker presents Codex as a competitive risk. They connect it to pressure on software companies."
        risk["detailedExplanation"] = "The speaker presents Codex as a competitive risk. They claim autonomous coding can replace parts of existing software workflows. This mechanism puts pressure on software companies. The implication in this section is commercial risk."
        ignored = {**candidate("S003", "S003", title="Minor aside"), "signalLevel": "low"}
        return [risk, ignored]

    async def generate_keyword_categories(self, occurrences, _language, _options):
        self.grouping_input = occurrences
        return [{"title": "OpenAI", "keywordIds": ["K001", "K002"]}]


class FixedTranscriptAnalyzeService(AnalyzeService):
    async def _resolve_transcript(self, _source, _emit):
        return ("Transcript text long enough for analysis. " * 4, "video123", [])


@pytest.mark.asyncio
async def test_analyze_returns_semantic_categories_with_distinct_contextual_occurrences() -> None:
    source_id, transcript_id = uuid4(), uuid4()
    segments = [
        TranscriptSegment(
            id=f"seg-{index}",
            source_id=source_id,
            transcript_id=transcript_id,
            sequence=index,
            start_time=[0, 46, 60, 312, 330, 400][index],
            end_time=[45, 59, 311, 329, 399, 430][index],
            raw_text=f"Raw {index}",
            text=f"Text {index}",
        )
        for index in range(6)
    ]
    store = ServiceStore(segments)
    llm = ServiceLlm()
    events: list[tuple[str, dict]] = []

    result = await FixedTranscriptAnalyzeService(store, llm, Settings()).analyze(
        {"type": "youtube", "youtubeUrl": "https://youtube.com/watch?v=video123"},
        lambda event, payload: events.append((event, payload)),
    )

    assert llm.extracted_titles == ["Introduction", "Competitive risk"]
    assert [item["keywordId"] for item in llm.grouping_input] == ["K001", "K002"]
    assert [item["term"] for item in llm.grouping_input] == ["Codex", "Codex"]
    assert len(store.saved_clippings) == 2
    assert result["categories"][0]["title"] == "OpenAI"
    assert "topicChunkId" not in result["categories"][0]
    first, second = result["categories"][0]["keywords"]
    assert first["candidateClippingId"] != second["candidateClippingId"]
    assert first["term"] == second["term"] == "Codex"
    assert first["level2"] != second["level2"]
    assert first["source"]["ref"].endswith("t=46s")
    assert second["source"]["ref"].endswith("t=312s")
    assert first["sources"] == [first["source"]]
    assert any(payload["stage"] == "grouping_keywords" for _, payload in events)
    assert store.completed is True
