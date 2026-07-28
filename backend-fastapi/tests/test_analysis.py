from uuid import uuid4

from app.analysis import build_topic_chunks, resolve_boundary_labels
from app.models import TranscriptSegment


def segment(sequence: int) -> TranscriptSegment:
    return TranscriptSegment(
        id=f"hash-{sequence}",
        source_id=uuid4(),
        transcript_id=uuid4(),
        sequence=sequence,
        start_time=sequence * 20,
        end_time=(sequence + 1) * 20,
        raw_text=f"Raw {sequence}",
        text=f"Text {sequence}",
    )


def test_resolves_labels_and_repairs_reversed_boundary() -> None:
    segments = [segment(0), segment(1)]
    boundaries = resolve_boundary_labels(
        [
            {
                "startSegmentId": "S002",
                "endSegmentId": "S001",
                "title": "A topic",
                "summary": "A grounded summary",
                "signalLevel": "high",
            }
        ],
        segments,
    )

    chunks, warnings = build_topic_chunks(
        boundaries, segments, uuid4(), uuid4(), uuid4()
    )

    assert chunks[0].start_segment_id == "hash-0"
    assert chunks[0].end_segment_id == "hash-1"
    assert warnings[0].reason == "reversed_topic_chunk_repaired"
