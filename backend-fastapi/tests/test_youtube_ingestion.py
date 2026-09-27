from uuid import UUID

import pytest

from app.errors import AppError
from app.store import StoredTranscript
from app.youtube import YoutubeTranscript
from app.youtube_ingestion import YoutubeTranscriptIngestionService

YOUTUBE_URL = "https://youtu.be/dQw4w9WgXcQ?feature=shared"
CANONICAL_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
TRANSCRIPT_ID = UUID("11111111-1111-4111-8111-111111111111")


class RecordingStore:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def set_transcript(self, **values) -> StoredTranscript:
        self.calls.append(values)
        return StoredTranscript(
            source_id=UUID("22222222-2222-4222-8222-222222222222"),
            transcript_id=TRANSCRIPT_ID,
            transcript_hash="hash",
        )

    async def create_analysis_run(self, *_args, **_kwargs):
        raise AssertionError("transcript ingestion must not create an analysis run")


def transcript(
    text: str,
    snippets: list[dict] | None = None,
) -> YoutubeTranscript:
    return YoutubeTranscript(
        video_id="dQw4w9WgXcQ",
        transcript_text=text,
        snippets=snippets
        if snippets is not None
        else [{"text": text, "start": 0, "duration": 4}],
        language_code="en",
        language="English",
        is_generated=False,
    )


@pytest.mark.asyncio
async def test_prepare_keeps_provider_text_without_segment_labels() -> None:
    provider_text = "The provider transcript should remain suitable for direct user display."

    prepared = await YoutubeTranscriptIngestionService(
        fetcher=lambda _url: transcript(provider_text)
    ).prepare(YOUTUBE_URL)

    assert prepared.user_transcript_text == provider_text
    assert "S001" not in prepared.user_transcript_text
    assert prepared.video_id == "dQw4w9WgXcQ"
    assert prepared.canonical_url == CANONICAL_URL
    assert prepared.language_code == "en"
    assert prepared.language == "English"
    assert prepared.is_generated is False


@pytest.mark.asyncio
async def test_prepare_builds_labeled_analysis_text_from_same_snippets() -> None:
    snippets = [
        {"text": "First idea", "start": 0, "duration": 4},
        {"text": "Second idea", "start": 5, "duration": 4},
    ]

    prepared = await YoutubeTranscriptIngestionService(
        fetcher=lambda _url: transcript("First idea Second idea", snippets)
    ).prepare(YOUTUBE_URL)

    assert prepared.analysis_transcript_text == "S001 | 00:00 | First idea Second idea"
    assert [item.raw_text for item in prepared.source_segments] == [
        "First idea",
        "Second idea",
    ]


@pytest.mark.asyncio
async def test_prepare_rejects_empty_user_transcript() -> None:
    service = YoutubeTranscriptIngestionService(fetcher=lambda _url: transcript("   "))

    with pytest.raises(AppError) as raised:
        await service.prepare(YOUTUBE_URL)

    assert raised.value.code == "EMPTY_TRANSCRIPT"


@pytest.mark.asyncio
async def test_prepare_keeps_noise_only_user_text_while_analysis_text_is_empty() -> None:
    service = YoutubeTranscriptIngestionService(
        fetcher=lambda _url: transcript(
            "[Music]",
            [{"text": "[Music]", "start": 0, "duration": 4}],
        )
    )

    prepared = await service.prepare(YOUTUBE_URL)

    assert prepared.user_transcript_text == "[Music]"
    assert prepared.analysis_transcript_text == ""
    assert prepared.source_segments == []


@pytest.mark.asyncio
async def test_ingest_stores_user_text_and_returns_that_row_id() -> None:
    store = RecordingStore()
    provider_text = "Transcript text stored without labels for the shared content note."

    response = await YoutubeTranscriptIngestionService(
        store=store,
        fetcher=lambda _url: transcript(provider_text),
    ).ingest(YOUTUBE_URL, "Shared video")

    assert len(store.calls) == 1
    assert {key: value for key, value in store.calls[0].items() if key != "source_segments"} == {
        "transcript_text": provider_text,
        "source_type": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "title": "Shared video",
        "youtube_url": CANONICAL_URL,
    }
    assert store.calls[0]["source_segments"][0].raw_text == provider_text
    assert response.transcriptId == str(TRANSCRIPT_ID)
    assert response.transcriptText == provider_text
    assert response.canonicalYoutubeUrl == CANONICAL_URL


@pytest.mark.asyncio
async def test_ingest_does_not_create_analysis_run_or_call_llm() -> None:
    store = RecordingStore()

    await YoutubeTranscriptIngestionService(
        store=store,
        fetcher=lambda _url: transcript("A transcript that is available without any LLM processing."),
    ).ingest(YOUTUBE_URL, None)

    assert len(store.calls) == 1


@pytest.mark.asyncio
async def test_ingest_preserves_language_metadata() -> None:
    response = await YoutubeTranscriptIngestionService(
        store=RecordingStore(),
        fetcher=lambda _url: transcript("Language metadata remains attached to the response."),
    ).ingest(YOUTUBE_URL, None)

    assert response.languageCode == "en"
    assert response.language == "English"
    assert response.isGenerated is False
    assert response.videoId == "dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_ingest_propagates_transcript_errors_without_store_write() -> None:
    store = RecordingStore()

    def unavailable(_url: str) -> YoutubeTranscript:
        raise AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video")

    with pytest.raises(AppError) as raised:
        await YoutubeTranscriptIngestionService(store=store, fetcher=unavailable).ingest(
            YOUTUBE_URL, None
        )

    assert raised.value.code == "TRANSCRIPT_UNAVAILABLE"
    assert store.calls == []
