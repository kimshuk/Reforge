from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("provider", "externalId"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    type: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    external_id: Mapped[str] = mapped_column("externalId", String, nullable=False)
    url: Mapped[str | None] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"
    __table_args__ = (UniqueConstraint("sourceId", "transcriptHash"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    source_id: Mapped[UUID] = mapped_column(
        "sourceId", ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    transcript_hash: Mapped[str] = mapped_column("transcriptHash", String, nullable=False)
    transcript_text: Mapped[str] = mapped_column("transcriptText", Text, nullable=False)
    video_id: Mapped[str | None] = mapped_column("videoId", String)
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TranscriptSegment(Base, TimestampMixin):
    __tablename__ = "transcript_segments"
    __table_args__ = (UniqueConstraint("transcriptId", "sequence"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[UUID] = mapped_column("sourceId", nullable=False)
    transcript_id: Mapped[UUID] = mapped_column(
        "transcriptId", ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[float] = mapped_column("startTime", Float, nullable=False)
    end_time: Mapped[float] = mapped_column("endTime", Float, nullable=False)
    raw_text: Mapped[str] = mapped_column("rawText", Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)


class AnalysisRun(Base, TimestampMixin):
    __tablename__ = "analysis_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    source_type: Mapped[str] = mapped_column("sourceType", String, nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(
        "sourceId", ForeignKey("sources.id", ondelete="SET NULL")
    )
    transcript_id: Mapped[UUID | None] = mapped_column(
        "transcriptId", ForeignKey("transcripts.id", ondelete="SET NULL")
    )
    transcript_hash: Mapped[str | None] = mapped_column("transcriptHash", String)
    status: Mapped[str] = mapped_column(String, nullable=False)
    failure_stage: Mapped[str | None] = mapped_column("failureStage", String)
    error_code: Mapped[str | None] = mapped_column("errorCode", String)
    safe_error_message: Mapped[str | None] = mapped_column("safeErrorMessage", String)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column("promptVersion", String, nullable=False)
    schema_version: Mapped[str] = mapped_column("schemaVersion", String, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    max_output_tokens: Mapped[int | None] = mapped_column("maxOutputTokens", Integer)
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TopicChunk(Base, TimestampMixin):
    __tablename__ = "topic_chunks"
    __table_args__ = (UniqueConstraint("analysisRunId", "sequence"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    source_id: Mapped[UUID] = mapped_column(
        "sourceId", ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    transcript_id: Mapped[UUID] = mapped_column(
        "transcriptId", ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        "analysisRunId", ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_segment_id: Mapped[str] = mapped_column("startSegmentId", String, nullable=False)
    end_segment_id: Mapped[str] = mapped_column("endSegmentId", String, nullable=False)
    start_time: Mapped[float] = mapped_column("startTime", Float, nullable=False)
    end_time: Mapped[float] = mapped_column("endTime", Float, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    signal_level: Mapped[str] = mapped_column("signalLevel", String, nullable=False)
    coverage_status: Mapped[str] = mapped_column(
        "coverageStatus", String, default="pending", nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)


class CandidateClipping(Base, TimestampMixin):
    __tablename__ = "candidate_clippings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    source_id: Mapped[UUID] = mapped_column(
        "sourceId", ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    transcript_id: Mapped[UUID] = mapped_column(
        "transcriptId", ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        "analysisRunId", ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    topic_chunk_id: Mapped[UUID] = mapped_column(
        "topicChunkId", ForeignKey("topic_chunks.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    brief: Mapped[str] = mapped_column(String, nullable=False)
    level1: Mapped[str] = mapped_column(Text, nullable=False)
    level2: Mapped[str] = mapped_column(Text, nullable=False)
    level3: Mapped[str] = mapped_column(Text, nullable=False)
    signal_level: Mapped[str] = mapped_column("signalLevel", String, nullable=False)
    source_ref_status: Mapped[str] = mapped_column("sourceRefStatus", String, nullable=False)
    source_refs: Mapped[list[dict[str, Any]]] = mapped_column(
        "sourceRefs", JSONB, nullable=False
    )


class KeywordCategory(Base, TimestampMixin):
    __tablename__ = "keyword_categories"
    __table_args__ = (
        UniqueConstraint("analysisRunId", "sequence"),
        UniqueConstraint("analysisRunId", "normalizedTitle"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    analysis_run_id: Mapped[UUID] = mapped_column(
        "analysisRunId", ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column("normalizedTitle", String, nullable=False)


class KeywordCategoryMembership(Base, TimestampMixin):
    __tablename__ = "keyword_category_memberships"
    __table_args__ = (
        UniqueConstraint("candidateClippingId"),
        UniqueConstraint("categoryId", "sequence"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    analysis_run_id: Mapped[UUID] = mapped_column(
        "analysisRunId", ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    category_id: Mapped[UUID] = mapped_column(
        "categoryId", ForeignKey("keyword_categories.id", ondelete="CASCADE"), nullable=False
    )
    candidate_clipping_id: Mapped[UUID] = mapped_column(
        "candidateClippingId", ForeignKey("candidate_clippings.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)


class CoverageWarning(Base, TimestampMixin):
    __tablename__ = "coverage_warnings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4, server_default=text("gen_random_uuid()"))
    source_id: Mapped[UUID] = mapped_column(
        "sourceId", ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    transcript_id: Mapped[UUID] = mapped_column(
        "transcriptId", ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[UUID] = mapped_column(
        "analysisRunId", ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    start_segment_id: Mapped[str | None] = mapped_column("startSegmentId", String)
    end_segment_id: Mapped[str | None] = mapped_column("endSegmentId", String)
    start_time: Mapped[float | None] = mapped_column("startTime", Float)
    end_time: Mapped[float | None] = mapped_column("endTime", Float)
    message: Mapped[str | None] = mapped_column(Text)


class EvalRun(Base, TimestampMixin):
    __tablename__ = "eval_runs"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column("promptVersion", String, nullable=False)
    schema_version: Mapped[str] = mapped_column("schemaVersion", String, nullable=False)
    transcript_hash: Mapped[str] = mapped_column("transcriptHash", String, nullable=False)
    latency_ms: Mapped[int] = mapped_column("latencyMs", Integer, nullable=False)
    estimated_cost: Mapped[str | None] = mapped_column("estimatedCost", String)
    validation_errors: Mapped[list[Any]] = mapped_column(
        "validationErrors", JSONB, nullable=False
    )
    raw_output: Mapped[dict[str, Any]] = mapped_column("rawOutput", JSONB, nullable=False)
    review: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
