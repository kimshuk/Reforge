from app.sanitizer import format_timestamp, normalize_text, sanitize_transcript


def test_sanitizes_noise_and_builds_stable_segment_labels() -> None:
    result = sanitize_transcript(
        [
            {"start": 0, "duration": 2, "text": "[Music]"},
            {"start": 2, "duration": 3, "text": "  > Hello   world  "},
        ]
    )

    assert result.cleaned_snippet_count == 1
    assert result.llm_transcript_text == "S001 | 00:02 | Hello world"


def test_formats_hour_timestamp() -> None:
    assert format_timestamp(3661.9) == "1:01:01"
    assert normalize_text("ㅋㅋㅋㅋㅋㅋ") == "ㅋㅋ"


def test_groups_short_snippets_for_llm_but_keeps_source_segments() -> None:
    result = sanitize_transcript(
        [
            {"start": 0, "duration": 8, "text": "First idea."},
            {"start": 8, "duration": 8, "text": "Second idea."},
            {"start": 16, "duration": 8, "text": "Third idea."},
        ]
    )

    assert result.llm_transcript_text == (
        "S001 | 00:00 | First idea. Second idea. Third idea."
    )
    assert len(result.source_segments) == 3
