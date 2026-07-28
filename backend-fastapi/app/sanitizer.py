import math
import re
from dataclasses import dataclass
from typing import Any

BRACKET_NOISE = re.compile(
    r"^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$",
    re.IGNORECASE,
)
MIN_SEGMENT_SECONDS = 20
MAX_SEGMENT_SECONDS = 35
HARD_MAX_SEGMENT_SECONDS = 45
MIN_SEGMENT_CHARS = 180
MAX_SEGMENT_CHARS = 320
HARD_MAX_SEGMENT_CHARS = 420
PAUSE_SPLIT_SECONDS = 2.5


@dataclass(frozen=True)
class CleanedSegment:
    sequence: int
    start_sec: float
    end_sec: float
    raw_text: str
    text: str


@dataclass(frozen=True)
class SanitizedTranscript:
    llm_transcript_text: str
    source_segments: list[CleanedSegment]
    cleaned_snippet_count: int


def format_timestamp(total_seconds: float) -> str:
    seconds = max(0, math.floor(total_seconds) if math.isfinite(total_seconds) else 0)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"


def normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = re.sub(r"^\s*>+\s*", " ", value)
    text = re.sub(
        r"\[([^\]]{1,30})\]|\(([^)]{1,30})\)",
        lambda match: " "
        if BRACKET_NOISE.match((match.group(1) or match.group(2) or "").strip())
        else match.group(0),
        text,
    )
    text = re.sub(r"ㅋ{3,}", "ㅋㅋ", text)
    text = re.sub(r"ㅎ{3,}", "ㅎㅎ", text)
    text = re.sub(r"([!?.,~])\1{2,}", r"\1\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if re.fullmatch(r"[>|~\-_=.,!?]+", text) else text


def sanitize_transcript(raw_snippets: Any) -> SanitizedTranscript:
    flattened: list[dict[str, Any]] = []

    def flatten(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                flatten(item)
        elif isinstance(value, dict):
            flattened.append(value)

    flatten(raw_snippets)
    cleaned: list[CleanedSegment] = []
    for item in flattened:
        try:
            start = float(item.get("start"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(start) or start < 0:
            continue
        try:
            duration = float(item.get("duration", 0))
        except (TypeError, ValueError):
            duration = 0
        duration = duration if math.isfinite(duration) and duration > 0 else 0
        text = normalize_text(item.get("text"))
        if not text:
            continue
        cleaned.append(
            CleanedSegment(
                sequence=0,
                start_sec=start,
                end_sec=start + duration,
                raw_text=str(item.get("text", "")).strip(),
                text=text,
            )
        )

    cleaned.sort(key=lambda item: item.start_sec)
    source_segments = [
        CleanedSegment(index, item.start_sec, item.end_sec, item.raw_text, item.text)
        for index, item in enumerate(cleaned)
    ]
    grouped: list[tuple[float, float, str]] = []
    current: list[CleanedSegment] = []
    for snippet in source_segments:
        if current and _should_split(current, snippet):
            grouped.append(_finalize(current))
            current = []
        current.append(snippet)
    if current:
        grouped.append(_finalize(current))
    lines = [
        f"S{index + 1:03d} | {format_timestamp(start)} | {text}"
        for index, (start, _end, text) in enumerate(grouped)
    ]
    return SanitizedTranscript("\n".join(lines), source_segments, len(source_segments))


def _should_split(current: list[CleanedSegment], next_segment: CleanedSegment) -> bool:
    start = current[0].start_sec
    end = max(item.end_sec for item in current)
    pause = next_segment.start_sec - end
    if pause > PAUSE_SPLIT_SECONDS:
        return True
    text = " ".join(item.text for item in current)
    next_end = max(end, next_segment.end_sec)
    next_duration = next_end - start
    next_chars = len(text) + 1 + len(next_segment.text)
    if next_duration <= MAX_SEGMENT_SECONDS and next_chars <= MAX_SEGMENT_CHARS:
        return False
    ready = end - start >= MIN_SEGMENT_SECONDS or len(text) >= MIN_SEGMENT_CHARS
    return ready or next_duration > HARD_MAX_SEGMENT_SECONDS or next_chars > HARD_MAX_SEGMENT_CHARS


def _finalize(segments: list[CleanedSegment]) -> tuple[float, float, str]:
    return (
        segments[0].start_sec,
        max(item.end_sec for item in segments),
        re.sub(r"\s+", " ", " ".join(item.text for item in segments)).strip(),
    )
