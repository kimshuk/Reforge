import { Injectable } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { createHash } from 'crypto';
import { Repository } from 'typeorm';

import { AnalysisRunEntity } from '../analyze/analysis-run.entity';
import { CandidateClippingEntity } from '../analyze/candidate-clipping.entity';
import { CoverageWarningEntity } from '../analyze/coverage-warning.entity';
import { TopicChunkEntity } from '../analyze/topic-chunk.entity';
import { LlmOptions, TranscriptType } from '../llm/llm.types';
import { SourceEntity } from './source.entity';
import { TranscriptSegmentEntity } from './transcript-segment.entity';
import { TranscriptEntity } from './transcript.entity';

export interface StoredTranscript {
  transcriptText: string;
  videoId: string | null;
  createdAt: number;
  expiresAt: number;
}

export interface TranscriptSegmentInput {
  sequence: number;
  startSec: number;
  endSec: number;
  rawText: string;
  text: string;
}

@Injectable()
export class TranscriptStoreService {
  readonly ttlMs = 1000 * 60 * 30;

  constructor(
    @InjectRepository(SourceEntity)
    private readonly sources: Repository<SourceEntity>,
    @InjectRepository(TranscriptEntity)
    private readonly transcripts: Repository<TranscriptEntity>,
    @InjectRepository(TranscriptSegmentEntity)
    private readonly segments: Repository<TranscriptSegmentEntity>,
    @InjectRepository(AnalysisRunEntity)
    private readonly analysisRuns: Repository<AnalysisRunEntity>,
    @InjectRepository(TopicChunkEntity)
    private readonly topicChunks: Repository<TopicChunkEntity>,
    @InjectRepository(CandidateClippingEntity)
    private readonly candidateClippings: Repository<CandidateClippingEntity>,
    @InjectRepository(CoverageWarningEntity)
    private readonly coverageWarnings: Repository<CoverageWarningEntity>,
  ) {}

  async createAnalysisRun(input: {
    sourceType: TranscriptType;
    llm: LlmOptions;
    promptVersion?: string;
    schemaVersion?: string;
  }): Promise<AnalysisRunEntity> {
    return this.analysisRuns.save(
      this.analysisRuns.create({
        sourceType: input.sourceType,
        sourceId: null,
        transcriptId: null,
        transcriptHash: null,
        status: 'running',
        failureStage: null,
        errorCode: null,
        safeErrorMessage: null,
        provider: input.llm.provider,
        model: input.llm.model,
        promptVersion: input.promptVersion ?? 'category-extraction-v1',
        schemaVersion: input.schemaVersion ?? 'category-extraction-v1',
        temperature: input.llm.temperature,
        maxOutputTokens: input.llm.maxOutputTokens ?? null,
      }),
    );
  }

  async markAnalysisRunTranscript(
    analysisRunId: string,
    input: { sourceId: string; transcriptId: string; transcriptHash: string },
  ): Promise<void> {
    await this.analysisRuns.update(analysisRunId, {
      sourceId: input.sourceId,
      transcriptId: input.transcriptId,
      transcriptHash: input.transcriptHash,
    });
  }

  async markAnalysisRunCompleted(analysisRunId: string): Promise<void> {
    await this.analysisRuns.update(analysisRunId, {
      status: 'completed',
      failureStage: null,
      errorCode: null,
      safeErrorMessage: null,
    });
  }

  async markAnalysisRunFailed(
    analysisRunId: string,
    input: { failureStage: string; errorCode: string; safeErrorMessage: string },
  ): Promise<void> {
    await this.analysisRuns.update(analysisRunId, {
      status: 'failed',
      failureStage: input.failureStage,
      errorCode: input.errorCode,
      safeErrorMessage: input.safeErrorMessage,
    });
  }

  async setTranscript(input: {
    transcriptText: string;
    sourceType: TranscriptType;
    videoId?: string | null;
    title?: string;
    youtubeUrl?: string;
    sourceSegments?: TranscriptSegmentInput[];
  }): Promise<{
    transcriptId: string;
    sourceId: string;
    transcriptHash: string;
  }> {
    const transcriptHash = this.hashTranscript(input.transcriptText);
    const source = await this.findOrCreateSource(input, transcriptHash);
    const transcript = await this.findOrCreateTranscript({
      source,
      transcriptText: input.transcriptText,
      transcriptHash,
      videoId: input.videoId ?? null,
    });

    const existingSegmentCount = await this.segments.countBy({
      transcriptId: transcript.id,
    });

    if (existingSegmentCount === 0) {
      await this.saveSegments({
        sourceId: source.id,
        transcriptId: transcript.id,
        transcriptHash,
        transcriptText: input.transcriptText,
        sourceSegments: input.sourceSegments ?? [],
      });
    }

    return {
      transcriptId: transcript.id,
      sourceId: source.id,
      transcriptHash,
    };
  }

  async getTranscript(transcriptId: string): Promise<StoredTranscript | null> {
    const transcript = await this.transcripts.findOneBy({ id: transcriptId });
    if (!transcript) {
      return null;
    }

    const createdAt = transcript.createdAt.getTime();
    return {
      transcriptText: transcript.transcriptText,
      videoId: transcript.videoId,
      createdAt,
      expiresAt: createdAt + this.ttlMs,
    };
  }

  async listSegments(transcriptId: string): Promise<TranscriptSegmentEntity[]> {
    return this.segments.find({
      where: { transcriptId },
      order: { sequence: 'ASC' },
    });
  }

  async saveTopicChunks(
    chunks: Array<Omit<TopicChunkEntity, 'id' | 'createdAt'>>,
  ): Promise<TopicChunkEntity[]> {
    if (!chunks.length) {
      return [];
    }

    return this.topicChunks.save(chunks.map((chunk) => this.topicChunks.create(chunk)));
  }

  async saveCandidateClippings(
    clippings: Array<Omit<CandidateClippingEntity, 'id' | 'createdAt'>>,
  ): Promise<CandidateClippingEntity[]> {
    if (!clippings.length) {
      return [];
    }

    return this.candidateClippings.save(
      clippings.map((clipping) => this.candidateClippings.create(clipping)),
    );
  }

  async saveCoverageWarnings(
    warnings: Array<Omit<CoverageWarningEntity, 'id' | 'createdAt'>>,
  ): Promise<CoverageWarningEntity[]> {
    if (!warnings.length) {
      return [];
    }

    return this.coverageWarnings.save(
      warnings.map((warning) => this.coverageWarnings.create(warning)),
    );
  }

  async updateTopicChunkCoverageStatuses(
    statuses: Array<{ id: string; coverageStatus: string }>,
  ): Promise<void> {
    await Promise.all(
      statuses.map((status) =>
        this.topicChunks.update(status.id, {
          coverageStatus: status.coverageStatus,
        }),
      ),
    );
  }

  private async findOrCreateSource(
    input: {
      sourceType: TranscriptType;
      videoId?: string | null;
      title?: string;
      youtubeUrl?: string;
    },
    transcriptHash: string,
  ): Promise<SourceEntity> {
    const provider = input.sourceType === 'youtube' ? 'youtube' : 'manual';
    const externalId =
      input.sourceType === 'youtube'
        ? (input.videoId ?? transcriptHash)
        : transcriptHash;

    const existing = await this.sources.findOneBy({ provider, externalId });
    if (existing) {
      return existing;
    }

    return this.sources.save(
      this.sources.create({
        type: input.sourceType,
        provider,
        externalId,
        url: input.youtubeUrl ?? null,
        title: input.title ?? null,
      }),
    );
  }

  private async findOrCreateTranscript(input: {
    source: SourceEntity;
    transcriptText: string;
    transcriptHash: string;
    videoId: string | null;
  }): Promise<TranscriptEntity> {
    const existing = await this.transcripts.findOneBy({
      sourceId: input.source.id,
      transcriptHash: input.transcriptHash,
    });
    if (existing) {
      return existing;
    }

    return this.transcripts.save(
      this.transcripts.create({
        sourceId: input.source.id,
        transcriptHash: input.transcriptHash,
        transcriptText: input.transcriptText,
        videoId: input.videoId,
      }),
    );
  }

  private async saveSegments(input: {
    sourceId: string;
    transcriptId: string;
    transcriptHash: string;
    transcriptText: string;
    sourceSegments: TranscriptSegmentInput[];
  }): Promise<void> {
    const segments = input.sourceSegments.length
      ? input.sourceSegments
      : [
          {
            sequence: 0,
            startSec: 0,
            endSec: 0,
            rawText: input.transcriptText,
            text: input.transcriptText,
          },
        ];

    await this.segments.save(
      segments.map((segment) =>
        this.segments.create({
          id: this.segmentId(input.transcriptHash, segment),
          sourceId: input.sourceId,
          transcriptId: input.transcriptId,
          sequence: segment.sequence,
          startTime: segment.startSec,
          endTime: segment.endSec,
          rawText: segment.rawText,
          text: segment.text,
        }),
      ),
    );
  }

  private hashTranscript(transcriptText: string): string {
    const normalized = transcriptText.replace(/\s+/g, ' ').trim();
    return createHash('sha256').update(normalized).digest('hex');
  }

  private segmentId(transcriptHash: string, segment: TranscriptSegmentInput): string {
    const stableInput = [
      transcriptHash,
      segment.sequence,
      segment.startSec,
      segment.endSec,
      segment.text.replace(/\s+/g, ' ').trim(),
    ].join('|');
    return `seg_${createHash('sha256').update(stableInput).digest('hex').slice(0, 32)}`;
  }
}
