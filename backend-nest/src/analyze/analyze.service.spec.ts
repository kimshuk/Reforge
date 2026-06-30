import { AnalyzeService } from './analyze.service';
import { CandidateClippingOutput, TopicChunkBoundary } from '../llm/llm.types';
import { TranscriptSegmentEntity } from '../transcript/transcript-segment.entity';

function service() {
  return new AnalyzeService(
    {} as any,
    {} as any,
    {} as any,
    {} as any,
    {} as any,
    {} as any,
  ) as any;
}

function segment(sequence: number): TranscriptSegmentEntity {
  return {
    id: `seg_${sequence}`,
    sourceId: 'source_1',
    transcriptId: 'transcript_1',
    sequence,
    startTime: sequence * 10,
    endTime: sequence * 10 + 9,
    rawText: `raw ${sequence}`,
    text: `text ${sequence}`,
    createdAt: new Date(0),
  } as TranscriptSegmentEntity;
}

function boundary(
  start: number,
  end: number,
  title = `Chunk ${start}-${end}`,
): TopicChunkBoundary {
  return {
    startSegmentId: `seg_${start}`,
    endSegmentId: `seg_${end}`,
    title,
    summary: title,
    signalLevel: 'high',
  };
}

describe('AnalyzeService topic chunk boundary validation', () => {
  it('sorts unordered non-overlapping model boundaries', () => {
    const result = service().buildTopicChunks({
      boundaries: [boundary(3, 4, 'Later'), boundary(0, 2, 'Earlier')],
      segments: [0, 1, 2, 3, 4].map(segment),
      sourceId: 'source_1',
      transcriptId: 'transcript_1',
      analysisRunId: 'run_1',
    });

    expect(result.chunks.map((chunk: { title: string }) => chunk.title)).toEqual([
      'Earlier',
      'Later',
    ]);
    expect(result.chunks.map((chunk: { sequence: number }) => chunk.sequence)).toEqual([
      0,
      1,
    ]);
    expect(result.warnings).toEqual([]);
  });

  it('repairs reversed model boundaries instead of failing the run', () => {
    const result = service().buildTopicChunks({
      boundaries: [boundary(3, 1, 'Reversed')],
      segments: [0, 1, 2, 3].map(segment),
      sourceId: 'source_1',
      transcriptId: 'transcript_1',
      analysisRunId: 'run_1',
    });

    expect(result.chunks).toHaveLength(1);
    expect(result.chunks[0]).toMatchObject({
      title: 'Reversed',
      startSegmentId: 'seg_1',
      endSegmentId: 'seg_3',
      text: 'text 1 text 2 text 3',
    });
    expect(result.warnings).toEqual([
      expect.objectContaining({
        reason: 'reversed_topic_chunk_repaired',
        startSegmentId: 'seg_3',
        endSegmentId: 'seg_1',
      }),
    ]);
  });

  it('trims partially overlapping boundaries instead of failing the run', () => {
    const result = service().buildTopicChunks({
      boundaries: [boundary(0, 2, 'First'), boundary(2, 4, 'Overlap')],
      segments: [0, 1, 2, 3, 4].map(segment),
      sourceId: 'source_1',
      transcriptId: 'transcript_1',
      analysisRunId: 'run_1',
    });

    expect(result.chunks).toHaveLength(2);
    expect(result.chunks[1]).toMatchObject({
      title: 'Overlap',
      startSegmentId: 'seg_3',
      endSegmentId: 'seg_4',
      text: 'text 3 text 4',
    });
    expect(result.warnings).toEqual([
      expect.objectContaining({
        reason: 'overlapping_topic_chunk_trimmed',
        startSegmentId: 'seg_2',
        endSegmentId: 'seg_4',
      }),
    ]);
  });

  it('keeps the widest chunk when boundaries share a start instead of truncating it', () => {
    const result = service().buildTopicChunks({
      boundaries: [boundary(0, 2, 'Narrow'), boundary(0, 4, 'Wide')],
      segments: [0, 1, 2, 3, 4].map(segment),
      sourceId: 'source_1',
      transcriptId: 'transcript_1',
      analysisRunId: 'run_1',
    });

    expect(result.chunks).toHaveLength(1);
    expect(result.chunks[0]).toMatchObject({
      title: 'Wide',
      startSegmentId: 'seg_0',
      endSegmentId: 'seg_4',
      text: 'text 0 text 1 text 2 text 3 text 4',
    });
    expect(result.warnings).toEqual([
      expect.objectContaining({
        reason: 'overlapping_topic_chunk_discarded',
        startSegmentId: 'seg_0',
        endSegmentId: 'seg_2',
      }),
    ]);
  });

  it('drops fully overlapping duplicate boundaries with a coverage warning', () => {
    const result = service().buildTopicChunks({
      boundaries: [boundary(0, 3, 'First'), boundary(1, 2, 'Duplicate')],
      segments: [0, 1, 2, 3].map(segment),
      sourceId: 'source_1',
      transcriptId: 'transcript_1',
      analysisRunId: 'run_1',
    });

    expect(result.chunks).toHaveLength(1);
    expect(result.chunks[0].title).toBe('First');
    expect(result.warnings).toEqual([
      expect.objectContaining({
        reason: 'overlapping_topic_chunk_discarded',
        startSegmentId: 'seg_1',
        endSegmentId: 'seg_2',
      }),
    ]);
  });
});

function candidate(
  refs: Array<{ startSegmentId: string; endSegmentId: string }>,
): CandidateClippingOutput {
  return {
    kind: 'term',
    title: 'Example',
    text: 'example text',
    brief: 'a short brief',
    simpleExplanation: 'simple',
    contextualExplanation: 'contextual',
    detailedExplanation: 'detailed',
    signalLevel: 'high',
    sourceRefs: refs.map((ref) => ({
      ...ref,
      timestamp: '00:00',
      text: 'ref text',
    })),
  };
}

describe('AnalyzeService segment id label contract', () => {
  it('formats prompt segments with stable S-labels instead of raw entity ids', () => {
    const lines = service()
      .formatSegmentsForPrompt([segment(0), segment(1)])
      .split('\n');

    expect(lines[0]).toMatch(/^S001 \| /);
    expect(lines[1]).toMatch(/^S002 \| /);
    expect(lines.join('\n')).not.toContain('seg_');
  });

  it('resolves topic boundary S-labels back to entity ids', () => {
    const resolved = service().resolveBoundaryLabels(
      [
        {
          startSegmentId: 'S001',
          endSegmentId: 'S003',
          title: 'Chunk',
          summary: 'Chunk',
          signalLevel: 'high',
        },
      ],
      [0, 1, 2].map(segment),
    );

    expect(resolved[0]).toMatchObject({
      startSegmentId: 'seg_0',
      endSegmentId: 'seg_2',
    });
  });

  it('passes unknown boundary labels through unchanged so validation still fails', () => {
    const resolved = service().resolveBoundaryLabels(
      [
        {
          startSegmentId: 'S999',
          endSegmentId: 'S001',
          title: 'Chunk',
          summary: 'Chunk',
          signalLevel: 'high',
        },
      ],
      [0, 1, 2].map(segment),
    );

    expect(resolved[0]).toMatchObject({
      startSegmentId: 'S999',
      endSegmentId: 'seg_0',
    });
  });

  it('resolves candidate source ref S-labels back to entity ids', () => {
    const resolved = service().resolveCandidateRefLabels(
      [candidate([{ startSegmentId: 'S001', endSegmentId: 'S002' }])],
      [0, 1, 2].map(segment),
    );

    expect(resolved[0].sourceRefs[0]).toMatchObject({
      startSegmentId: 'seg_0',
      endSegmentId: 'seg_1',
    });
  });

  it('resolves boundary labels even when the model drops the S prefix', () => {
    const resolved = service().resolveBoundaryLabels(
      [
        {
          startSegmentId: '1',
          endSegmentId: '003',
          title: 'Chunk',
          summary: 'Chunk',
          signalLevel: 'high',
        },
      ],
      [0, 1, 2].map(segment),
    );

    expect(resolved[0]).toMatchObject({
      startSegmentId: 'seg_0',
      endSegmentId: 'seg_2',
    });
  });

  it('resolves candidate refs even when the model drops the S prefix', () => {
    const resolved = service().resolveCandidateRefLabels(
      [candidate([{ startSegmentId: '022', endSegmentId: '023' }])],
      Array.from({ length: 25 }, (_, sequence) => segment(sequence)),
    );

    expect(resolved[0].sourceRefs[0]).toMatchObject({
      startSegmentId: 'seg_21',
      endSegmentId: 'seg_22',
    });
  });
});
