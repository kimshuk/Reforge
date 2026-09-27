import pytest

from app.errors import AppError
from app.youtube import YoutubeTranscript
from app.youtube_ingestion import YoutubeTranscriptIngestionService

YOUTUBE_URL = "https://youtu.be/dQw4w9WgXcQ?feature=shared"
CANONICAL_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


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

