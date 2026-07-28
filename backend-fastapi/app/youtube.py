import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from youtube_transcript_api import TranscriptsDisabled, VideoUnavailable, YouTubeTranscriptApi

from app.errors import AppError


@dataclass(frozen=True)
class YoutubeTranscript:
    video_id: str
    transcript_text: str
    snippets: list[dict[str, Any]]
    language_code: str | None
    language: str | None
    is_generated: bool | None


class TimeoutSession(requests.Session):
    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", (10, 30))
        return super().request(method, url, **kwargs)


def extract_video_id(youtube_url: str) -> str:
    try:
        parsed = urlparse(youtube_url)
    except ValueError as error:
        raise AppError(400, "INVALID_YOUTUBE_URL", "youtubeUrl must be a valid URL") from error
    host = (parsed.hostname or "").removeprefix("www.").lower()
    if parsed.scheme.lower() not in {"http", "https"}:
        raise AppError(400, "INVALID_YOUTUBE_URL", "youtubeUrl must use http or https")
    video_id: str | None = None
    if host == "youtu.be" and parsed.path.strip("/"):
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com"}:
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if not video_id and parsed.path.startswith("/shorts/") and len(parsed.path.split("/")) > 2:
            video_id = parsed.path.split("/")[2]
    if video_id and re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
        return video_id
    raise AppError(400, "INVALID_YOUTUBE_URL", "Unsupported YouTube URL format")


def fetch_youtube_transcript(youtube_url: str) -> YoutubeTranscript:
    video_id = extract_video_id(youtube_url)
    try:
        with TimeoutSession() as session:
            transcripts = list(YouTubeTranscriptApi(http_client=session).list(video_id))
            if not transcripts:
                raise AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video")
            selected = next((item for item in transcripts if not item.is_generated), transcripts[0])
            raw = selected.fetch().to_raw_data()
    except (TranscriptsDisabled, VideoUnavailable) as error:
        raise AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video") from error
    except AppError:
        raise
    except Exception as error:
        raise AppError(502, "TRANSCRIPT_FETCH_FAILED", "Unable to fetch YouTube transcript") from error
    snippets = [item for item in raw if isinstance(item, dict) and str(item.get("text", "")).strip()]
    transcript_text = " ".join(str(item["text"]).strip() for item in snippets)
    if not transcript_text:
        raise AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video")
    return YoutubeTranscript(
        video_id=video_id,
        transcript_text=transcript_text,
        snippets=snippets,
        language_code=getattr(selected, "language_code", None),
        language=getattr(selected, "language", None),
        is_generated=getattr(selected, "is_generated", None),
    )
