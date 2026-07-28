import pytest

from app.errors import AppError
from app.youtube import extract_video_id


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ],
)
def test_extracts_supported_video_urls(url: str) -> None:
    assert extract_video_id(url) == "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        "javascript://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://example.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=short",
    ],
)
def test_rejects_unsafe_or_invalid_video_urls(url: str) -> None:
    with pytest.raises(AppError) as raised:
        extract_video_id(url)

    assert raised.value.code == "INVALID_YOUTUBE_URL"
