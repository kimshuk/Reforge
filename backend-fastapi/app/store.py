import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AnalysisRun,
    CandidateClipping,
    CoverageWarning,
    Source,
    TopicChunk,
    Transcript,
    TranscriptSegment,
)
from app.sanitizer import CleanedSegment

TRANSCRIPT_TTL_SECONDS = 30 * 60


@dataclass(frozen=True)
class StoredTranscript:
    source_id: UUID
    transcript_id: UUID
    transcript_hash: str


class TranscriptStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_analysis_run(self, source_type: str, llm: dict[str, Any]) -> AnalysisRun:
        run = AnalysisRun(
            source_type=source_type,
            status="running",
            provider=llm["provider"],
            model=llm["model"],
            prompt_version="segment-grounded-clipping-v1",
            schema_version="segment-grounded-clipping-v1",
            temperature=llm["temperature"],
            max_output_tokens=llm.get("maxOutputTokens"),
        )
        self.db.add(run)
        await self.db.commit()
        return run

    async def set_transcript(
        self,
        *,
        transcript_text: str,
        source_type: str,
        video_id: str | None,
        title: str | None,
        youtube_url: str | None,
        source_segments: list[CleanedSegment],
    ) -> StoredTranscript:
        normalized = re.sub(r"\s+", " ", transcript_text).strip()
        transcript_hash = hashlib.sha256(normalized.encode()).hexdigest()
        provider = "youtube" if source_type == "youtube" else "manual"
        external_id = video_id or transcript_hash

        await self.db.execute(
            insert(Source)
            .values(
                id=uuid4(),
                type=source_type,
                provider=provider,
                externalId=external_id,
                url=youtube_url,
                title=title,
            )
            .on_conflict_do_nothing(index_elements=[Source.provider, Source.external_id])
        )
        await self.db.commit()
        source = await self.db.scalar(
            select(Source).where(Source.provider == provider, Source.external_id == external_id)
        )
        assert source is not None

        await self.db.execute(
            insert(Transcript)
            .values(
                id=uuid4(),
                sourceId=source.id,
                transcriptHash=transcript_hash,
                transcriptText=transcript_text,
                videoId=video_id,
            )
            .on_conflict_do_nothing(
                index_elements=[Transcript.source_id, Transcript.transcript_hash]
            )
        )
        await self.db.commit()
        transcript = await self.db.scalar(
            select(Transcript).where(
                Transcript.source_id == source.id,
                Transcript.transcript_hash == transcript_hash,
            )
        )
        assert transcript is not None

        segments = source_segments or [CleanedSegment(0, 0, 0, transcript_text, transcript_text)]
        rows = []
        for segment in segments:
            stable_input = "|".join(
                [
                    transcript_hash,
                    str(segment.sequence),
                    str(segment.start_sec),
                    str(segment.end_sec),
                    re.sub(r"\s+", " ", segment.text).strip(),
                ]
            )
            rows.append(
                {
                    "id": f"seg_{hashlib.sha256(stable_input.encode()).hexdigest()[:32]}",
                    "sourceId": source.id,
                    "transcriptId": transcript.id,
                    "sequence": segment.sequence,
                    "startTime": segment.start_sec,
                    "endTime": segment.end_sec,
                    "rawText": segment.raw_text,
                    "text": segment.text,
                }
            )
        await self.db.execute(insert(TranscriptSegment).values(rows).on_conflict_do_nothing())
        await self.db.commit()
        return StoredTranscript(source.id, transcript.id, transcript_hash)

    async def list_segments(self, transcript_id: UUID) -> list[TranscriptSegment]:
        result = await self.db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
            .order_by(TranscriptSegment.sequence)
        )
        segments = list(result)
        await self.db.commit()
        return segments

    async def get_transcript(self, transcript_id: UUID) -> Transcript | None:
        transcript = await self.db.get(Transcript, transcript_id)
        await self.db.commit()
        return transcript

    async def save_chunks(self, chunks: list[TopicChunk]) -> list[TopicChunk]:
        self.db.add_all(chunks)
        await self.db.commit()
        return chunks

    async def save_clippings(self, clippings: list[CandidateClipping]) -> list[CandidateClipping]:
        self.db.add_all(clippings)
        await self.db.commit()
        return clippings

    async def save_warnings(self, warnings: list[CoverageWarning]) -> None:
        if warnings:
            self.db.add_all(warnings)
            await self.db.commit()

    async def mark_transcript(self, run: AnalysisRun, stored: StoredTranscript) -> None:
        run.source_id = stored.source_id
        run.transcript_id = stored.transcript_id
        run.transcript_hash = stored.transcript_hash
        await self.db.commit()

    async def mark_completed(self, run: AnalysisRun) -> None:
        run.status = "completed"
        run.failure_stage = run.error_code = run.safe_error_message = None
        await self.db.commit()

    async def mark_failed(self, run: AnalysisRun, stage: str, code: str, message: str) -> None:
        await self.db.rollback()
        run = await self.db.merge(run)
        run.status = "failed"
        run.failure_stage = stage
        run.error_code = code
        run.safe_error_message = message
        await self.db.commit()


def transcript_expiry(transcript: Transcript) -> tuple[str, str]:
    created = transcript.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    created = created.astimezone(UTC)
    expires = created + timedelta(seconds=TRANSCRIPT_TTL_SECONDS)
    return _iso_utc(created), _iso_utc(expires)


def _iso_utc(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
