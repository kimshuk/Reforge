import { Injectable, Logger } from '@nestjs/common';

import { AppException } from '../common/app.exception';
import { CandidateClippingEntity } from './candidate-clipping.entity';
import { LlmConfigService } from '../llm/llm-config.service';
import { LlmService } from '../llm/llm.service';
import { CandidateClippingOutput, TopicChunkBoundary } from '../llm/llm.types';
import { TranscriptSegmentEntity } from '../transcript/transcript-segment.entity';
import { TranscriptStoreService } from '../transcript/transcript-store.service';
import { AnalyzeRequestParser } from './analyze-request.parser';
import { AnalyzeSource } from './analyze.types';
import {
  CleanedTranscriptSegment,
  formatTimestamp,
  TranscriptSanitizer,
} from './transcript.sanitizer';
import { YoutubeService } from './youtube.service';

type ProgressEmitter = (event: string, payload: Record<string, unknown>) => void;

interface BuiltTopicChunk {
  sourceId: string;
  transcriptId: string;
  analysisRunId: string;
  sequence: number;
  startSegmentId: string;
  endSegmentId: string;
  startTime: number;
  endTime: number;
  title: string;
  summary: string;
  signalLevel: string;
  coverageStatus: string;
  text: string;
}

interface CoverageWarningInput {
  sourceId: string;
  transcriptId: string;
  analysisRunId: string;
  reason: string;
  startSegmentId: string | null;
  endSegmentId: string | null;
  startTime: number | null;
  endTime: number | null;
  message: string | null;
}

interface ResolvedTopicBoundary {
  boundary: TopicChunkBoundary;
  start: TranscriptSegmentEntity;
  end: TranscriptSegmentEntity;
}

@Injectable()
export class AnalyzeService {
  private readonly logger = new Logger(AnalyzeService.name);

  constructor(
    private readonly parser: AnalyzeRequestParser,
    private readonly youtubeService: YoutubeService,
    private readonly sanitizer: TranscriptSanitizer,
    private readonly transcriptStore: TranscriptStoreService,
    private readonly llmConfig: LlmConfigService,
    private readonly llmService: LlmService,
  ) {}

  async analyze(
    body: unknown,
    requestId?: string,
    emitProgress?: ProgressEmitter,
  ) {
    const source = this.parser.parse(body);
    const llmOptions = this.llmConfig.resolve(source);
    const analysisRun = await this.transcriptStore.createAnalysisRun({
      sourceType: source.type,
      llm: llmOptions,
      promptVersion: 'segment-grounded-clipping-v1',
      schemaVersion: 'segment-grounded-clipping-v1',
    });
    let failureStage = 'started';

    try {
      this.logger.log({
        event: 'analyze.request',
        requestId,
        analysisRunId: analysisRun.id,
        type: source.type,
        targetLanguage: source.targetLanguage,
        hasYoutubeUrl: source.type === 'youtube',
        hasText: source.type === 'manual',
        hasTitle: Boolean(source.title),
        llm: llmOptions,
      });

      emitProgress?.('started', {
        stage: 'started',
        message: 'Accepted analyze request',
        type: source.type,
        llm: llmOptions,
      });

      failureStage =
        source.type === 'youtube' ? 'fetching_transcript' : 'validating_transcript';
      const transcript = await this.resolveTranscript(source, requestId, emitProgress);
      const normalizedTranscript = this.parser.assertTranscriptText(
        transcript.transcriptText,
      );

      emitProgress?.('progress', {
        stage: 'creating_segments',
        message: 'Creating stable transcript segments',
      });

      failureStage = 'storing_transcript';
      const storedTranscript = await this.transcriptStore.setTranscript({
        transcriptText: normalizedTranscript,
        sourceType: source.type,
        videoId: transcript.videoId,
        title: source.title,
        youtubeUrl: source.type === 'youtube' ? source.youtubeUrl : undefined,
        sourceSegments: transcript.sourceSegments,
      });
      await this.transcriptStore.markAnalysisRunTranscript(analysisRun.id, {
        sourceId: storedTranscript.sourceId,
        transcriptId: storedTranscript.transcriptId,
        transcriptHash: storedTranscript.transcriptHash,
      });

      const transcriptSegments = await this.transcriptStore.listSegments(
        storedTranscript.transcriptId,
      );

      emitProgress?.('progress', {
        stage: 'chunking_topics',
        message: 'Identifying transcript topic chunks',
        transcriptId: storedTranscript.transcriptId,
        segmentCount: transcriptSegments.length,
      });

      failureStage = 'chunking_topics';
      const topicBoundaries = await this.llmService.generateTopicChunks({
        transcriptSegments: this.formatSegmentsForPrompt(transcriptSegments),
        targetLanguage: source.targetLanguage,
        options: llmOptions,
      });

      emitProgress?.('progress', {
        stage: 'validating_chunks',
        message: 'Validating topic chunk boundaries',
        topicChunkCount: topicBoundaries.length,
      });

      failureStage = 'validating_chunks';
      const { chunks, warnings } = this.buildTopicChunks({
        boundaries: topicBoundaries,
        segments: transcriptSegments,
        sourceId: storedTranscript.sourceId,
        transcriptId: storedTranscript.transcriptId,
        analysisRunId: analysisRun.id,
      });
      const savedChunks = await this.transcriptStore.saveTopicChunks(chunks);
      await this.transcriptStore.saveCoverageWarnings(warnings);

      emitProgress?.('progress', {
        stage: 'extracting_clippings',
        message: 'Extracting candidate clippings',
        topicChunkCount: savedChunks.length,
      });

      failureStage = 'extracting_clippings';
      const clippings: Array<Omit<CandidateClippingEntity, 'id' | 'createdAt'>> = [];
      const segmentsById = new Map(transcriptSegments.map((segment) => [segment.id, segment]));

      for (const chunk of savedChunks.filter((item) => item.signalLevel === 'high')) {
        const chunkSegments = this.segmentsForRange(
          transcriptSegments,
          chunk.startSegmentId,
          chunk.endSegmentId,
        );
        const candidates = await this.llmService.generateCandidateClippings({
          chunkTitle: chunk.title,
          chunkSummary: chunk.summary,
          chunkSegments: this.formatSegmentsForPrompt(chunkSegments),
          targetLanguage: source.targetLanguage,
          options: llmOptions,
        });

        clippings.push(
          ...candidates.map((candidate) =>
            this.toCandidateClippingEntity({
              candidate,
              chunk,
              segmentsById,
              source,
              sourceId: storedTranscript.sourceId,
              transcriptId: storedTranscript.transcriptId,
              analysisRunId: analysisRun.id,
            }),
          ),
        );
      }

      const savedClippings = await this.transcriptStore.saveCandidateClippings(
        clippings,
      );
      const extractionWarnings = this.reviewChunkCoverage({
        chunks: savedChunks,
        clippings: savedClippings,
        segments: transcriptSegments,
        sourceId: storedTranscript.sourceId,
        transcriptId: storedTranscript.transcriptId,
        analysisRunId: analysisRun.id,
      });
      await this.transcriptStore.saveCoverageWarnings(extractionWarnings);
      await this.transcriptStore.updateTopicChunkCoverageStatuses(
        this.topicChunkCoverageStatuses(savedChunks, extractionWarnings),
      );

      emitProgress?.('progress', {
        stage: 'reviewing_coverage',
        message: 'Reviewing topic coverage',
        warningCount: warnings.length + extractionWarnings.length,
      });

      emitProgress?.('progress', {
        stage: 'storing_analysis',
        message: 'Storing analysis artifacts',
      });

      const response = {
        transcriptId: storedTranscript.transcriptId,
        sourceType: source.type,
        categories: savedChunks.map((chunk) => ({
          title: chunk.title,
          topicChunkId: chunk.id,
          keywords: savedClippings
            .filter((clipping) => clipping.topicChunkId === chunk.id)
            .map((clipping) => ({
              term: clipping.title,
              candidateClippingId: clipping.id,
              brief: clipping.brief,
              level1: clipping.level1,
              level2: clipping.level2,
              level3: clipping.level3,
              source: {
                type: source.type,
                ref: clipping.sourceRefs[0]?.ref ?? '',
              },
            })),
        })),
        expiresInSeconds: this.transcriptStore.ttlMs / 1000,
        llm: llmOptions,
        ...(transcript.videoId ? { videoId: transcript.videoId } : {}),
      };

      await this.transcriptStore.markAnalysisRunCompleted(analysisRun.id);

      emitProgress?.('completed', {
        stage: 'completed',
        message: 'Analysis complete',
        transcriptId: storedTranscript.transcriptId,
        categoryCount: response.categories.length,
      });

      return response;
    } catch (error) {
      await this.markRunFailed(analysisRun.id, failureStage, error);
      throw error;
    }
  }

  private async resolveTranscript(
    source: AnalyzeSource,
    requestId: string | undefined,
    emitProgress?: ProgressEmitter,
  ): Promise<{
    transcriptText: string;
    videoId: string | null;
    segmentIndex: ReturnType<TranscriptSanitizer['sanitize']>['segmentIndex'];
    sourceSegments: CleanedTranscriptSegment[];
  }> {
    if (source.type === 'manual') {
      return {
        transcriptText: source.text ?? '',
        videoId: null,
        segmentIndex: [],
        sourceSegments: [],
      };
    }

    emitProgress?.('progress', {
      stage: 'fetching_transcript',
      message: 'Fetching YouTube transcript',
    });

    const youtubeResult = await this.youtubeService.fetchTranscript(
      source.youtubeUrl ?? '',
    );

    emitProgress?.('progress', {
      stage: 'sanitizing_transcript',
      message: 'Preparing transcript for analysis',
      videoId: youtubeResult.videoId,
    });

    const sanitized = this.sanitizer.sanitize(youtubeResult.transcriptSnippets);

    this.logger.log({
      event: 'analyze.transcript_language',
      requestId,
      videoId: youtubeResult.videoId,
      languageCode: youtubeResult.languageCode,
      language: youtubeResult.language,
      isGenerated: youtubeResult.isGenerated,
      snippetCount: youtubeResult.transcriptSnippets.length,
      cleanedSnippetCount: sanitized.cleanedSnippetCount,
      segmentCount: sanitized.segmentIndex.length,
    });

    emitProgress?.('progress', {
      stage: 'transcript_ready',
      message: 'Transcript prepared',
      videoId: youtubeResult.videoId,
      segmentCount: sanitized.segmentIndex.length,
    });

    return {
      transcriptText: sanitized.llmTranscriptText,
      videoId: youtubeResult.videoId,
      segmentIndex: sanitized.segmentIndex,
      sourceSegments: sanitized.sourceSegments,
    };
  }

  private buildTopicChunks(input: {
    boundaries: TopicChunkBoundary[];
    segments: TranscriptSegmentEntity[];
    sourceId: string;
    transcriptId: string;
    analysisRunId: string;
  }): { chunks: BuiltTopicChunk[]; warnings: CoverageWarningInput[] } {
    const segmentsById = new Map(input.segments.map((segment) => [segment.id, segment]));
    const chunks: BuiltTopicChunk[] = [];
    const warnings: CoverageWarningInput[] = [];
    let previousEndSequence = -1;
    const resolvedBoundaries = input.boundaries.map((boundary) => {
      let start = segmentsById.get(boundary.startSegmentId);
      let end = segmentsById.get(boundary.endSegmentId);
      if (!start || !end) {
        throw new AppException(
          502,
          'LLM_TOPIC_CHUNKS_INVALID_BOUNDARY',
          'Model returned unknown topic chunk segment id',
        );
      }

      if (start.sequence > end.sequence) {
        warnings.push(
          this.boundaryWarning({
            reason: 'reversed_topic_chunk_repaired',
            sourceId: input.sourceId,
            transcriptId: input.transcriptId,
            analysisRunId: input.analysisRunId,
            start,
            end,
            message: 'Model returned a reversed topic chunk range; backend swapped the boundary order',
          }),
        );
        [start, end] = [end, start];
      }

      return { boundary, start, end };
    });

    resolvedBoundaries.sort((left, right) => {
      if (left.start.sequence !== right.start.sequence) {
        return left.start.sequence - right.start.sequence;
      }
      return left.end.sequence - right.end.sequence;
    });

    for (const resolved of resolvedBoundaries) {
      const boundary = resolved.boundary;
      let start = resolved.start;
      const end = resolved.end;

      if (start.sequence <= previousEndSequence) {
        if (end.sequence <= previousEndSequence) {
          warnings.push(
            this.boundaryWarning({
              reason: 'overlapping_topic_chunk_discarded',
              sourceId: input.sourceId,
              transcriptId: input.transcriptId,
              analysisRunId: input.analysisRunId,
              start,
              end,
              message: 'Model returned a topic chunk fully covered by an earlier chunk',
            }),
          );
          continue;
        }

        const adjustedStart = input.segments.find(
          (segment) => segment.sequence === previousEndSequence + 1,
        );
        if (!adjustedStart) {
          warnings.push(
            this.boundaryWarning({
              reason: 'overlapping_topic_chunk_discarded',
              sourceId: input.sourceId,
              transcriptId: input.transcriptId,
              analysisRunId: input.analysisRunId,
              start,
              end,
              message: 'Model returned a topic chunk overlap that could not be repaired',
            }),
          );
          continue;
        }

        warnings.push(
          this.boundaryWarning({
            reason: 'overlapping_topic_chunk_trimmed',
            sourceId: input.sourceId,
            transcriptId: input.transcriptId,
            analysisRunId: input.analysisRunId,
            start,
            end,
            message: 'Model returned an overlapping topic chunk; backend trimmed it to the next uncovered segment',
          }),
        );
        start = adjustedStart;
      }

      if (start.sequence > previousEndSequence + 1) {
        const gap = this.gapWarning({
          segments: input.segments,
          startSequence: previousEndSequence + 1,
          endSequence: start.sequence - 1,
          sourceId: input.sourceId,
          transcriptId: input.transcriptId,
          analysisRunId: input.analysisRunId,
        });
        if (gap) {
          warnings.push(gap);
        }
      }

      const chunkSegments = this.segmentsInSequenceRange(
        input.segments,
        start.sequence,
        end.sequence,
      );
      chunks.push({
        sourceId: input.sourceId,
        transcriptId: input.transcriptId,
        analysisRunId: input.analysisRunId,
        sequence: chunks.length,
        startSegmentId: start.id,
        endSegmentId: end.id,
        startTime: start.startTime,
        endTime: end.endTime,
        title: boundary.title,
        summary: boundary.summary,
        signalLevel: boundary.signalLevel,
        coverageStatus: 'pending',
        text: chunkSegments.map((segment) => segment.text).join(' ').trim(),
      });

      previousEndSequence = end.sequence;
    }

    if (previousEndSequence < input.segments.length - 1) {
      const gap = this.gapWarning({
        segments: input.segments,
        startSequence: previousEndSequence + 1,
        endSequence: input.segments.length - 1,
        sourceId: input.sourceId,
        transcriptId: input.transcriptId,
        analysisRunId: input.analysisRunId,
      });
      if (gap) {
        warnings.push(gap);
      }
    }

    return { chunks, warnings };
  }

  private gapWarning(input: {
    segments: TranscriptSegmentEntity[];
    startSequence: number;
    endSequence: number;
    sourceId: string;
    transcriptId: string;
    analysisRunId: string;
  }): CoverageWarningInput | null {
    const start = input.segments[input.startSequence];
    const end = input.segments[input.endSequence];
    if (!start || !end) {
      return null;
    }

    const duration = Math.max(0, end.endTime - start.startTime);
    const segmentCount = input.endSequence - input.startSequence + 1;
    if (duration <= 30 && segmentCount <= 5) {
      return null;
    }

    return {
      sourceId: input.sourceId,
      transcriptId: input.transcriptId,
      analysisRunId: input.analysisRunId,
      reason: 'major_gap',
      startSegmentId: start.id,
      endSegmentId: end.id,
      startTime: start.startTime,
      endTime: end.endTime,
      message: 'Uncovered transcript range exceeded the major gap threshold',
    };
  }

  private boundaryWarning(input: {
    reason: string;
    sourceId: string;
    transcriptId: string;
    analysisRunId: string;
    start: TranscriptSegmentEntity;
    end: TranscriptSegmentEntity;
    message: string;
  }): CoverageWarningInput {
    return {
      sourceId: input.sourceId,
      transcriptId: input.transcriptId,
      analysisRunId: input.analysisRunId,
      reason: input.reason,
      startSegmentId: input.start.id,
      endSegmentId: input.end.id,
      startTime: input.start.startTime,
      endTime: input.end.endTime,
      message: input.message,
    };
  }

  private toCandidateClippingEntity(input: {
    candidate: CandidateClippingOutput;
    chunk: BuiltTopicChunk & { id: string };
    segmentsById: Map<string, TranscriptSegmentEntity>;
    source: AnalyzeSource;
    sourceId: string;
    transcriptId: string;
    analysisRunId: string;
  }): Omit<CandidateClippingEntity, 'id' | 'createdAt'> {
    const chunkStart = input.segmentsById.get(input.chunk.startSegmentId);
    const chunkEnd = input.segmentsById.get(input.chunk.endSegmentId);
    const sourceRefs = input.candidate.sourceRefs
      .map((ref) => {
        const start = input.segmentsById.get(ref.startSegmentId);
        const end = input.segmentsById.get(ref.endSegmentId);
        if (
          !start ||
          !end ||
          !chunkStart ||
          !chunkEnd ||
          start.sequence > end.sequence ||
          start.sequence < chunkStart.sequence ||
          end.sequence > chunkEnd.sequence
        ) {
          return null;
        }

        return {
          startSegmentId: start.id,
          endSegmentId: end.id,
          timestamp: formatTimestamp(start.startTime),
          ref: this.sourceRef(input.source, start.startTime, ref.text),
          text: ref.text,
        };
      })
      .filter((ref): ref is NonNullable<typeof ref> => Boolean(ref));

    const finalSourceRefs = sourceRefs.length
      ? sourceRefs
      : [
          {
            startSegmentId: input.chunk.startSegmentId,
            endSegmentId: input.chunk.endSegmentId,
            timestamp: formatTimestamp(input.chunk.startTime),
            ref: this.sourceRef(input.source, input.chunk.startTime, input.chunk.text),
            text: input.chunk.text.slice(0, 300),
          },
        ];

    return {
      sourceId: input.sourceId,
      transcriptId: input.transcriptId,
      analysisRunId: input.analysisRunId,
      topicChunkId: input.chunk.id,
      kind: input.candidate.kind,
      title: input.candidate.title,
      text: input.candidate.text,
      brief: input.candidate.brief,
      level1: input.candidate.simpleExplanation,
      level2: input.candidate.contextualExplanation,
      level3: input.candidate.detailedExplanation,
      signalLevel: input.candidate.signalLevel,
      sourceRefStatus: sourceRefs.length ? 'precise' : 'chunk_level',
      sourceRefs: finalSourceRefs,
    };
  }

  private segmentsForRange(
    segments: TranscriptSegmentEntity[],
    startSegmentId: string,
    endSegmentId: string,
  ): TranscriptSegmentEntity[] {
    const start = segments.find((segment) => segment.id === startSegmentId);
    const end = segments.find((segment) => segment.id === endSegmentId);
    if (!start || !end) {
      return [];
    }

    return this.segmentsInSequenceRange(segments, start.sequence, end.sequence);
  }

  private segmentsInSequenceRange(
    segments: TranscriptSegmentEntity[],
    startSequence: number,
    endSequence: number,
  ): TranscriptSegmentEntity[] {
    return segments.filter(
      (segment) => segment.sequence >= startSequence && segment.sequence <= endSequence,
    );
  }

  private reviewChunkCoverage(input: {
    chunks: Array<BuiltTopicChunk & { id: string }>;
    clippings: CandidateClippingEntity[];
    segments: TranscriptSegmentEntity[];
    sourceId: string;
    transcriptId: string;
    analysisRunId: string;
  }): CoverageWarningInput[] {
    const warnings: CoverageWarningInput[] = [];
    const clippingsByChunk = new Map<string, CandidateClippingEntity[]>();
    for (const clipping of input.clippings) {
      const list = clippingsByChunk.get(clipping.topicChunkId) ?? [];
      list.push(clipping);
      clippingsByChunk.set(clipping.topicChunkId, list);
    }

    for (const chunk of input.chunks) {
      if (chunk.signalLevel !== 'high') {
        continue;
      }

      const chunkSegments = this.segmentsForRange(
        input.segments,
        chunk.startSegmentId,
        chunk.endSegmentId,
      );
      const clippingCount = clippingsByChunk.get(chunk.id)?.length ?? 0;
      const duration = Math.max(0, chunk.endTime - chunk.startTime);
      const isBroadChunk = duration > 180 || chunkSegments.length > 20;

      if (clippingCount === 0 || (isBroadChunk && clippingCount < 2)) {
        warnings.push({
          sourceId: input.sourceId,
          transcriptId: input.transcriptId,
          analysisRunId: input.analysisRunId,
          reason: 'weak_candidate_extraction',
          startSegmentId: chunk.startSegmentId,
          endSegmentId: chunk.endSegmentId,
          startTime: chunk.startTime,
          endTime: chunk.endTime,
          message:
            clippingCount === 0
              ? 'High-signal topic chunk produced no candidate clippings'
              : 'Broad high-signal topic chunk produced few candidate clippings',
        });
      }
    }

    return warnings;
  }

  private topicChunkCoverageStatuses(
    chunks: Array<BuiltTopicChunk & { id: string }>,
    warnings: CoverageWarningInput[],
  ): Array<{ id: string; coverageStatus: string }> {
    return chunks.map((chunk) => {
      const hasWeakExtractionWarning = warnings.some(
        (warning) =>
          warning.reason === 'weak_candidate_extraction' &&
          warning.startSegmentId === chunk.startSegmentId &&
          warning.endSegmentId === chunk.endSegmentId,
      );

      if (hasWeakExtractionWarning) {
        return { id: chunk.id, coverageStatus: 'weak_candidate_extraction' };
      }
      if (chunk.signalLevel === 'off_topic') {
        return { id: chunk.id, coverageStatus: 'off_topic' };
      }
      if (chunk.signalLevel === 'low') {
        return { id: chunk.id, coverageStatus: 'low_signal' };
      }
      if (chunk.signalLevel === 'medium') {
        return { id: chunk.id, coverageStatus: 'represented' };
      }

      return { id: chunk.id, coverageStatus: 'covered' };
    });
  }

  private formatSegmentsForPrompt(segments: TranscriptSegmentEntity[]): string {
    return segments
      .map(
        (segment) =>
          `${segment.id} | ${formatTimestamp(segment.startTime)} | ${segment.text}`,
      )
      .join('\n');
  }

  private sourceRef(source: AnalyzeSource, startTime: number, text: string): string {
    if (source.type !== 'youtube' || !source.youtubeUrl) {
      return text.slice(0, 240);
    }

    const url = new URL(source.youtubeUrl);
    url.searchParams.set('t', `${Math.max(0, Math.floor(startTime))}s`);
    return url.toString();
  }

  private async markRunFailed(
    analysisRunId: string,
    failureStage: string,
    error: unknown,
  ): Promise<void> {
    const appError =
      error instanceof AppException
        ? error
        : new AppException(500, 'INTERNAL_SERVER_ERROR', 'Unexpected server error');

    try {
      await this.transcriptStore.markAnalysisRunFailed(analysisRunId, {
        failureStage,
        errorCode: appError.code,
        safeErrorMessage: appError.message,
      });
    } catch (updateError) {
      this.logger.error({
        event: 'analyze.analysis_run_failed_update_failed',
        analysisRunId,
        failureStage,
        error: updateError instanceof Error ? updateError.message : String(updateError),
      });
    }
  }
}
