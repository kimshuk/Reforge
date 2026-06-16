#!/usr/bin/env python3
import json
import sys

try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, VideoUnavailable
except Exception:
    print(
        json.dumps(
            {
                "error": "PY_DEP_MISSING",
                "message": "youtube-transcript-api is not installed",
            }
        ),
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            json.dumps({"error": "INVALID_ARGS", "message": "video_id argument is required"}),
            file=sys.stderr,
        )
        return 2

    video_id = (sys.argv[1] or "").strip()
    if not video_id:
        print(
            json.dumps({"error": "INVALID_VIDEO_ID", "message": "video_id must be non-empty"}),
            file=sys.stderr,
        )
        return 2

    transcript_api = YouTubeTranscriptApi()
    try:
        transcript_list = transcript_api.list(video_id)
    except (TranscriptsDisabled, VideoUnavailable) as exc:
        print(
            json.dumps({"error": "TRANSCRIPT_UNAVAILABLE", "message": str(exc)}),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            json.dumps({"error": "TRANSCRIPT_FETCH_FAILED", "message": str(exc)}),
            file=sys.stderr,
        )
        return 1

    transcripts = list(transcript_list)
    if not transcripts:
        print(
            json.dumps(
                {
                    "error": "TRANSCRIPT_UNAVAILABLE",
                    "message": "No transcript tracks available",
                }
            ),
            file=sys.stderr,
        )
        return 1

    selected = next((t for t in transcripts if not getattr(t, "is_generated", False)), None)
    if selected is None:
        selected = transcripts[0]

    try:
        transcript = selected.fetch().to_raw_data()
    except Exception as exc:
        print(
            json.dumps({"error": "TRANSCRIPT_FETCH_FAILED", "message": str(exc)}),
            file=sys.stderr,
        )
        return 1

    parts = []
    normalized_snippets = []
    for snippet in transcript:
        if not isinstance(snippet, dict):
            continue

        text = snippet.get("text")
        if isinstance(text, str):
            cleaned = text.strip()
            if cleaned:
                parts.append(cleaned)
                start = snippet.get("start")
                duration = snippet.get("duration")
                normalized_snippets.append(
                    {
                        "start": start if isinstance(start, (int, float)) else 0,
                        "duration": duration if isinstance(duration, (int, float)) else 0,
                        "text": cleaned,
                    }
                )

    print(
        json.dumps(
            {
                "transcriptText": " ".join(parts),
                "transcriptSnippets": normalized_snippets,
                "languageCode": getattr(selected, "language_code", None),
                "language": getattr(selected, "language", None),
                "isGenerated": bool(getattr(selected, "is_generated", False)),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
