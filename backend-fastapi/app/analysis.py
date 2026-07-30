import asyncio
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import UUID

from app.config import Settings
from app.errors import AppError
from app.llm import LlmClient, normalize_segment_ref, resolve_llm_options
from app.models import (
    CandidateClipping,
    CoverageWarning,
    KeywordCategory,
    TopicChunk,
    TranscriptSegment,
)
from app.sanitizer import (
    CleanedSegment,
    format_timestamp,
    sanitize_transcript,
    segment_manual_transcript,
)
from app.schemas import AnalyzeResult, AnalyzeSource, assert_transcript_text, parse_analyze_request
from app.store import TRANSCRIPT_TTL_SECONDS, TranscriptStore
from app.youtube import fetch_youtube_transcript

ProgressEmitter = Callable[[str, dict[str, Any]], None]


class AnalyzeService:
    def __init__(self, store: TranscriptStore, llm: LlmClient, settings: Settings) -> None:
        self.store = store
        self.llm = llm
        self.settings = settings

    async def analyze(
        self, body: Any, emit: ProgressEmitter | None = None
    ) -> dict[str, Any]:
        source = parse_analyze_request(body, self.settings)
        llm_options = resolve_llm_options(source, self.settings)
        run = await self.store.create_analysis_run(source.type, llm_options)
        failure_stage = "started"
        try:
            _emit(emit, "started", stage="started", message="Accepted analyze request", type=source.type, llm=llm_options)
            failure_stage = "fetching_transcript" if source.type == "youtube" else "validating_transcript"
            transcript_text, video_id, source_segments = await self._resolve_transcript(source, emit)
            normalized = assert_transcript_text(transcript_text)
            _emit(emit, "progress", stage="creating_segments", message="Creating stable transcript segments")

            failure_stage = "storing_transcript"
            stored = await self.store.set_transcript(
                transcript_text=normalized,
                source_type=source.type,
                video_id=video_id,
                title=source.title,
                youtube_url=source.youtube_url,
                source_segments=source_segments,
            )
            await self.store.mark_transcript(run, stored)
            segments = await self.store.list_segments(stored.transcript_id)

            _emit(
                emit,
                "progress",
                stage="chunking_topics",
                message="Identifying transcript topic chunks",
                transcriptId=str(stored.transcript_id),
                segmentCount=len(segments),
            )
            failure_stage = "chunking_topics"
            formatted_segments = format_segments(segments)
            boundaries = await self.llm.generate_topic_chunks(
                formatted_segments, source.target_language, llm_options
            )
            _emit(
                emit,
                "progress",
                stage="validating_chunks",
                message="Validating topic chunk boundaries",
                topicChunkCount=len(boundaries),
            )
            failure_stage = "validating_chunks"
            boundaries = resolve_boundary_labels(boundaries, segments)
            chunks, warnings = build_topic_chunks(
                boundaries, segments, stored.source_id, stored.transcript_id, run.id
            )
            saved_chunks = await self.store.save_chunks(chunks)
            await self.store.save_warnings(warnings)

            _emit(
                emit,
                "progress",
                stage="extracting_clippings",
                message="Extracting candidate clippings",
                topicChunkCount=len(saved_chunks),
            )
            failure_stage = "extracting_clippings"
            segments_by_id = {segment.id: segment for segment in segments}
            clippings: list[CandidateClipping] = []
            extracted_occurrence_count = 0
            filtered_occurrence_count = 0
            for chunk in eligible_topic_chunks(saved_chunks):
                chunk_segments = segments_for_range(segments, chunk.start_segment_id, chunk.end_segment_id)
                candidates = await self.llm.generate_candidate_clippings(
                    chunk.title,
                    chunk.summary,
                    format_segments(chunk_segments),
                    source.target_language,
                    llm_options,
                )
                resolved_candidates = resolve_candidate_labels(candidates, segments)
                extracted_occurrence_count += len(resolved_candidates)
                for candidate in resolved_candidates:
                    if candidate["signalLevel"] == "low":
                        filtered_occurrence_count += 1
                        continue
                    clippings.append(
                        candidate_entity(
                            candidate,
                            chunk,
                            segments_by_id,
                            source,
                            stored.source_id,
                            stored.transcript_id,
                            run.id,
                        )
                    )
            _emit(
                emit,
                "progress",
                stage="deduplicating_occurrences",
                message="Removing exact duplicate keyword occurrences",
                extractedOccurrenceCount=extracted_occurrence_count,
                filteredOccurrenceCount=filtered_occurrence_count,
            )
            failure_stage = "deduplicating_occurrences"
            retained_clippings = deduplicate_occurrences(clippings)
            grouping_input, occurrences_by_id = build_grouping_occurrences(retained_clippings)

            grouping: list[dict[str, Any]] = []
            _emit(
                emit,
                "progress",
                stage="grouping_keywords",
                message="Assigning keyword occurrences to semantic categories",
                retainedOccurrenceCount=len(retained_clippings),
                exactDuplicateCount=len(clippings) - len(retained_clippings),
            )
            failure_stage = "grouping_keywords"
            if grouping_input:
                grouping = await self.llm.generate_keyword_categories(
                    grouping_input,
                    source.target_language,
                    llm_options,
                )
            _emit(
                emit,
                "progress",
                stage="grouping_keywords",
                message="Keyword occurrence grouping complete",
                extractedOccurrenceCount=extracted_occurrence_count,
                filteredOccurrenceCount=filtered_occurrence_count,
                exactDuplicateCount=len(clippings) - len(retained_clippings),
                retainedOccurrenceCount=len(retained_clippings),
                groupedOccurrenceCount=sum(
                    len(category["keywordIds"]) for category in grouping
                ),
                discardedOccurrenceCount=(
                    filtered_occurrence_count
                    + len(clippings)
                    - len(retained_clippings)
                ),
            )
            extraction_warnings = review_coverage(
                saved_chunks,
                retained_clippings,
                segments,
                stored.source_id,
                stored.transcript_id,
                run.id,
            )
            await self.store.save_warnings(extraction_warnings)
            set_coverage_statuses(saved_chunks, extraction_warnings)

            _emit(
                emit,
                "progress",
                stage="reviewing_coverage",
                message="Reviewing topic coverage",
                warningCount=len(warnings) + len(extraction_warnings),
            )
            _emit(emit, "progress", stage="storing_analysis", message="Storing analysis artifacts")
            failure_stage = "storing_analysis"
            saved_clippings, saved_categories, _memberships = await self.store.save_category_graph(
                run.id,
                retained_clippings,
                grouping,
                occurrences_by_id,
            )
            response = build_analysis_result(
                stored.transcript_id,
                source,
                video_id,
                llm_options,
                grouping,
                saved_categories,
                occurrences_by_id,
            )
            await self.store.mark_completed(run)
            _emit(
                emit,
                "completed",
                stage="completed",
                message="Analysis complete",
                transcriptId=str(stored.transcript_id),
                categoryCount=len(saved_categories),
                keywordOccurrenceCount=len(saved_clippings),
            )
            return response
        except asyncio.CancelledError:
            await self.store.mark_failed(
                run,
                failure_stage,
                "ANALYSIS_CANCELLED",
                "Analysis was cancelled before completion",
            )
            raise
        except Exception as error:
            app_error = error if isinstance(error, AppError) else AppError(500, "INTERNAL_SERVER_ERROR", "Unexpected server error")
            await self.store.mark_failed(run, failure_stage, app_error.code, app_error.message)
            raise

    async def _resolve_transcript(
        self, source: AnalyzeSource, emit: ProgressEmitter | None
    ) -> tuple[str, str | None, list[CleanedSegment]]:
        if source.type == "manual":
            text = source.text or ""
            return text, None, segment_manual_transcript(text)
        _emit(emit, "progress", stage="fetching_transcript", message="Fetching YouTube transcript")
        result = await asyncio.to_thread(fetch_youtube_transcript, source.youtube_url or "")
        source.youtube_url = f"https://www.youtube.com/watch?v={result.video_id}"
        _emit(
            emit,
            "progress",
            stage="sanitizing_transcript",
            message="Preparing transcript for analysis",
            videoId=result.video_id,
        )
        sanitized = sanitize_transcript(result.snippets)
        _emit(
            emit,
            "progress",
            stage="transcript_ready",
            message="Transcript prepared",
            videoId=result.video_id,
            segmentCount=sanitized.cleaned_snippet_count,
        )
        return sanitized.llm_transcript_text, result.video_id, sanitized.source_segments


def format_segments(segments: list[TranscriptSegment]) -> str:
    return "\n".join(
        f"S{segment.sequence + 1:03d} | {format_timestamp(segment.start_time)} | {segment.text}"
        for segment in segments
    )


def label_map(segments: list[TranscriptSegment]) -> dict[str, str]:
    return {
        normalize_segment_ref(f"S{segment.sequence + 1:03d}"): segment.id
        for segment in segments
    }


def resolve_boundary_labels(boundaries: list[dict[str, Any]], segments: list[TranscriptSegment]) -> list[dict[str, Any]]:
    labels = label_map(segments)
    return [
        {
            **boundary,
            "startSegmentId": labels.get(normalize_segment_ref(boundary["startSegmentId"]), boundary["startSegmentId"]),
            "endSegmentId": labels.get(normalize_segment_ref(boundary["endSegmentId"]), boundary["endSegmentId"]),
        }
        for boundary in boundaries
    ]


def resolve_candidate_labels(candidates: list[dict[str, Any]], segments: list[TranscriptSegment]) -> list[dict[str, Any]]:
    labels = label_map(segments)
    return [
        {
            **candidate,
            "sourceRefs": [
                {
                    **ref,
                    "startSegmentId": labels.get(normalize_segment_ref(ref["startSegmentId"]), ref["startSegmentId"]),
                    "endSegmentId": labels.get(normalize_segment_ref(ref["endSegmentId"]), ref["endSegmentId"]),
                }
                for ref in candidate["sourceRefs"]
            ],
        }
        for candidate in candidates
    ]


def eligible_topic_chunks(chunks: list[TopicChunk]) -> list[TopicChunk]:
    return [item for item in chunks if item.signal_level in {"high", "medium"}]


def deduplicate_occurrences(clippings: list[CandidateClipping]) -> list[CandidateClipping]:
    retained: list[CandidateClipping] = []
    seen: set[tuple[str, str, str]] = set()
    for clipping in clippings:
        if not clipping.source_refs:
            raise AppError(502, "LLM_CLIPPINGS_INVALID_SOURCE_REF", "Keyword occurrence has no source reference")
        primary = clipping.source_refs[0]
        start_id, end_id = primary.get("startSegmentId"), primary.get("endSegmentId")
        if not isinstance(start_id, str) or not isinstance(end_id, str):
            raise AppError(502, "LLM_CLIPPINGS_INVALID_SOURCE_REF", "Keyword occurrence has an invalid source range")
        normalized_term = re.sub(r"\s+", " ", clipping.title).strip().casefold()
        key = (normalized_term, start_id, end_id)
        if key in seen:
            continue
        seen.add(key)
        retained.append(clipping)
    return retained


def build_grouping_occurrences(
    clippings: list[CandidateClipping],
) -> tuple[list[dict[str, str]], dict[str, CandidateClipping]]:
    metadata: list[dict[str, str]] = []
    by_id: dict[str, CandidateClipping] = {}
    for index, clipping in enumerate(clippings, start=1):
        keyword_id = f"K{index:03d}"
        primary = clipping.source_refs[0]
        metadata.append(
            {
                "keywordId": keyword_id,
                "term": clipping.title,
                "kind": clipping.kind,
                "brief": clipping.brief,
                "contextualExplanation": clipping.level2,
                "timestamp": str(primary.get("timestamp", "")),
            }
        )
        by_id[keyword_id] = clipping
    return metadata, by_id


def build_analysis_result(
    transcript_id: UUID,
    source: AnalyzeSource,
    video_id: str | None,
    llm_options: dict[str, Any],
    grouping: list[dict[str, Any]],
    categories: list[KeywordCategory],
    occurrences_by_id: dict[str, CandidateClipping],
) -> dict[str, Any]:
    if len(grouping) != len(categories):
        raise AppError(500, "INVALID_CATEGORY_GRAPH", "Persisted categories do not match grouping output")
    category_results = []
    for grouped, category in zip(grouping, categories, strict=True):
        keyword_results = []
        for keyword_id in grouped["keywordIds"]:
            clipping = occurrences_by_id[keyword_id]
            sources = [
                {"type": source.type, "ref": str(item.get("ref", ""))}
                for item in clipping.source_refs
                if item.get("ref")
            ]
            keyword_results.append(
                {
                    "term": clipping.title,
                    "candidateClippingId": str(clipping.id),
                    "brief": clipping.brief,
                    "level1": clipping.level1,
                    "level2": clipping.level2,
                    "level3": clipping.level3,
                    "source": sources[0] if sources else {"type": source.type, "ref": ""},
                    "sources": sources,
                }
            )
        category_results.append(
            {
                "categoryId": str(category.id),
                "title": category.title,
                "keywords": keyword_results,
            }
        )
    return AnalyzeResult.model_validate(
        {
            "transcriptId": str(transcript_id),
            "sourceType": source.type,
            "categories": category_results,
            "expiresInSeconds": TRANSCRIPT_TTL_SECONDS,
            "llm": llm_options,
            "videoId": video_id,
        }
    ).model_dump(mode="json", exclude_none=True)


def build_topic_chunks(
    boundaries: list[dict[str, Any]],
    segments: list[TranscriptSegment],
    source_id: UUID,
    transcript_id: UUID,
    run_id: UUID,
) -> tuple[list[TopicChunk], list[CoverageWarning]]:
    by_id = {segment.id: segment for segment in segments}
    resolved: list[tuple[dict[str, Any], TranscriptSegment, TranscriptSegment]] = []
    warnings: list[CoverageWarning] = []
    for boundary in boundaries:
        start, end = by_id.get(boundary["startSegmentId"]), by_id.get(boundary["endSegmentId"])
        if not start or not end:
            raise AppError(502, "LLM_TOPIC_CHUNKS_INVALID_BOUNDARY", "Model returned unknown topic chunk segment id")
        if start.sequence > end.sequence:
            warnings.append(boundary_warning("reversed_topic_chunk_repaired", source_id, transcript_id, run_id, start, end, "Model returned a reversed topic chunk range; backend swapped the boundary order"))
            start, end = end, start
        resolved.append((boundary, start, end))
    resolved.sort(key=lambda item: (item[1].sequence, -item[2].sequence))

    chunks: list[TopicChunk] = []
    previous_end = -1
    for boundary, start, end in resolved:
        if start.sequence <= previous_end:
            if end.sequence <= previous_end:
                warnings.append(boundary_warning("overlapping_topic_chunk_discarded", source_id, transcript_id, run_id, start, end, "Model returned a topic chunk fully covered by an earlier chunk"))
                continue
            adjusted = next((item for item in segments if item.sequence == previous_end + 1), None)
            if not adjusted:
                continue
            warnings.append(boundary_warning("overlapping_topic_chunk_trimmed", source_id, transcript_id, run_id, start, end, "Model returned an overlapping topic chunk; backend trimmed it to the next uncovered segment"))
            start = adjusted
        if start.sequence > previous_end + 1:
            warning = gap_warning(segments, previous_end + 1, start.sequence - 1, source_id, transcript_id, run_id)
            if warning:
                warnings.append(warning)
        chunk_segments = [item for item in segments if start.sequence <= item.sequence <= end.sequence]
        chunks.append(
            TopicChunk(
                source_id=source_id,
                transcript_id=transcript_id,
                analysis_run_id=run_id,
                sequence=len(chunks),
                start_segment_id=start.id,
                end_segment_id=end.id,
                start_time=start.start_time,
                end_time=end.end_time,
                title=boundary["title"],
                summary=boundary["summary"],
                signal_level=boundary["signalLevel"],
                coverage_status="pending",
                text=" ".join(item.text for item in chunk_segments).strip(),
            )
        )
        previous_end = end.sequence
    if previous_end < len(segments) - 1:
        warning = gap_warning(segments, previous_end + 1, len(segments) - 1, source_id, transcript_id, run_id)
        if warning:
            warnings.append(warning)
    return chunks, warnings


def gap_warning(segments: list[TranscriptSegment], start_index: int, end_index: int, source_id: UUID, transcript_id: UUID, run_id: UUID) -> CoverageWarning | None:
    start = next((item for item in segments if item.sequence == start_index), None)
    end = next((item for item in segments if item.sequence == end_index), None)
    if not start or not end or (max(0, end.end_time - start.start_time) <= 30 and end_index - start_index + 1 <= 5):
        return None
    return CoverageWarning(source_id=source_id, transcript_id=transcript_id, analysis_run_id=run_id, reason="major_gap", start_segment_id=start.id, end_segment_id=end.id, start_time=start.start_time, end_time=end.end_time, message="Uncovered transcript range exceeded the major gap threshold")


def boundary_warning(reason: str, source_id: UUID, transcript_id: UUID, run_id: UUID, start: TranscriptSegment, end: TranscriptSegment, message: str) -> CoverageWarning:
    return CoverageWarning(source_id=source_id, transcript_id=transcript_id, analysis_run_id=run_id, reason=reason, start_segment_id=start.id, end_segment_id=end.id, start_time=start.start_time, end_time=end.end_time, message=message)


def candidate_entity(candidate: dict[str, Any], chunk: TopicChunk, segments_by_id: dict[str, TranscriptSegment], source: AnalyzeSource, source_id: UUID, transcript_id: UUID, run_id: UUID) -> CandidateClipping:
    chunk_start, chunk_end = segments_by_id.get(chunk.start_segment_id), segments_by_id.get(chunk.end_segment_id)
    source_refs = []
    for ref in candidate["sourceRefs"]:
        start, end = segments_by_id.get(ref["startSegmentId"]), segments_by_id.get(ref["endSegmentId"])
        if not start or not end or not chunk_start or not chunk_end or start.sequence > end.sequence or start.sequence < chunk_start.sequence or end.sequence > chunk_end.sequence:
            raise AppError(502, "LLM_CLIPPINGS_INVALID_SOURCE_REF", "Keyword source reference is outside its topic chunk")
        grounded_segments = sorted(
            (
                item
                for item in segments_by_id.values()
                if start.sequence <= item.sequence <= end.sequence
            ),
            key=lambda item: item.sequence,
        )
        grounded_text = " ".join(item.text for item in grounded_segments).strip()
        source_refs.append({
            "startSegmentId": start.id,
            "endSegmentId": end.id,
            "timestamp": format_timestamp(start.start_time),
            "ref": source_ref(source, start.start_time, grounded_text),
            "text": grounded_text[:300],
        })
    if not source_refs:
        raise AppError(502, "LLM_CLIPPINGS_INVALID_SOURCE_REF", "Keyword occurrence has no valid source reference")
    return CandidateClipping(
        source_id=source_id,
        transcript_id=transcript_id,
        analysis_run_id=run_id,
        topic_chunk_id=chunk.id,
        kind=candidate["kind"],
        title=candidate["title"],
        text=candidate["text"],
        brief=candidate["brief"],
        level1=candidate["simpleExplanation"],
        level2=candidate["contextualExplanation"],
        level3=candidate["detailedExplanation"],
        signal_level=candidate["signalLevel"],
        source_ref_status="precise",
        source_refs=source_refs,
    )


def source_ref(source: AnalyzeSource, start_time: float, text: str) -> str:
    if source.type != "youtube" or not source.youtube_url:
        return text[:240]
    parsed = urlparse(source.youtube_url)
    query = dict(parse_qsl(parsed.query))
    query["t"] = f"{max(0, int(start_time))}s"
    return urlunparse(parsed._replace(query=urlencode(query)))


def segments_for_range(segments: list[TranscriptSegment], start_id: str, end_id: str) -> list[TranscriptSegment]:
    start = next((item for item in segments if item.id == start_id), None)
    end = next((item for item in segments if item.id == end_id), None)
    return [] if not start or not end else [item for item in segments if start.sequence <= item.sequence <= end.sequence]


def review_coverage(chunks: list[TopicChunk], clippings: list[CandidateClipping], segments: list[TranscriptSegment], source_id: UUID, transcript_id: UUID, run_id: UUID) -> list[CoverageWarning]:
    warnings = []
    for chunk in eligible_topic_chunks(chunks):
        count = sum(1 for item in clippings if item.topic_chunk_id == chunk.id)
        broad = chunk.end_time - chunk.start_time > 180 or len(segments_for_range(segments, chunk.start_segment_id, chunk.end_segment_id)) > 20
        if count == 0 or broad and count < 2:
            warnings.append(CoverageWarning(source_id=source_id, transcript_id=transcript_id, analysis_run_id=run_id, reason="weak_candidate_extraction", start_segment_id=chunk.start_segment_id, end_segment_id=chunk.end_segment_id, start_time=chunk.start_time, end_time=chunk.end_time, message="Eligible topic chunk produced no keyword occurrences" if count == 0 else "Broad eligible topic chunk produced few keyword occurrences"))
    return warnings


def set_coverage_statuses(chunks: list[TopicChunk], warnings: list[CoverageWarning]) -> None:
    for chunk in chunks:
        weak = any(item.reason == "weak_candidate_extraction" and item.start_segment_id == chunk.start_segment_id and item.end_segment_id == chunk.end_segment_id for item in warnings)
        chunk.coverage_status = "weak_candidate_extraction" if weak else "off_topic" if chunk.signal_level == "off_topic" else "low_signal" if chunk.signal_level == "low" else "represented" if chunk.signal_level == "medium" else "covered"


def _emit(emit: ProgressEmitter | None, event: str, **payload: Any) -> None:
    if emit:
        emit(event, payload)
