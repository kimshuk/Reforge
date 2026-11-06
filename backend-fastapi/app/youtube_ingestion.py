import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from app.sanitizer import CleanedSegment, sanitize_transcript
from app.schemas import YoutubeTranscriptResponse, assert_transcript_available
from app.youtube import YoutubeTranscript, fetch_youtube_transcript


@dataclass(frozen=True)
class PreparedYoutubeTranscript:
    video_id: str
    canonical_url: str
    user_transcript_text: str
    analysis_transcript_text: str
    source_segments: list[CleanedSegment]
    language_code: str | None
    language: str | None
    is_generated: bool | None


class YoutubeTranscriptIngestionService:
    def __init__(
        self,
        fetcher: Callable[[str], YoutubeTranscript] = fetch_youtube_transcript,
    ) -> None:
        self.fetcher = fetcher

    async def prepare(self, youtube_url: str) -> PreparedYoutubeTranscript:
        result = await asyncio.to_thread(self.fetcher, youtube_url)
        user_text = assert_transcript_available(result.transcript_text)
        sanitized = sanitize_transcript(result.snippets)
        return PreparedYoutubeTranscript(
            video_id=result.video_id,
            canonical_url=f"https://www.youtube.com/watch?v={result.video_id}",
            user_transcript_text=user_text,
            analysis_transcript_text=sanitized.llm_transcript_text,
            source_segments=sanitized.source_segments,
            language_code=result.language_code,
            language=result.language,
            is_generated=result.is_generated,
        )

    async def ingest(self, youtube_url: str) -> YoutubeTranscriptResponse:
        prepared = await self.prepare(youtube_url)
        return YoutubeTranscriptResponse(
            videoId=prepared.video_id,
            canonicalYoutubeUrl=prepared.canonical_url,
            transcriptText=prepared.user_transcript_text,
            languageCode=prepared.language_code,
            language=prepared.language,
            isGenerated=prepared.is_generated,
        )
