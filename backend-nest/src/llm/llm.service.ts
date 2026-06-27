import { Inject, Injectable, Logger } from '@nestjs/common';

import { formatTimestamp, SegmentIndexEntry } from '../analyze/transcript.sanitizer';
import { AppException } from '../common/app.exception';
import {
  buildCandidateClippingPrompt,
  CANDIDATE_CLIPPING_SCHEMA,
} from './candidate-clipping.prompt';
import { buildCategoryExtractionPrompt } from './category-extraction.prompt';
import { buildTranscriptSummaryPrompt } from './transcript-summary.prompt';
import {
  buildTopicChunkingPrompt,
  TOPIC_CHUNKING_SCHEMA,
} from './topic-chunking.prompt';
import {
  AnalysisWithLlmSettings,
  CandidateClippingOutput,
  CategoryAnalysis,
  CategoryKeyword,
  GenerateAnalysisInput,
  GenerateSummaryInput,
  LlmProviderAdapter,
  SummaryWithLlmSettings,
  TranscriptSummary,
  TopicChunkBoundary,
} from './llm.types';

export const LLM_ADAPTERS = Symbol('LLM_ADAPTERS');

@Injectable()
export class LlmService {
  private readonly logger = new Logger(LlmService.name);

  constructor(
    @Inject(LLM_ADAPTERS)
    private readonly adapters: LlmProviderAdapter[],
  ) {}

  async generateTopicChunks(input: {
    transcriptSegments: string;
    targetLanguage: string;
    options: GenerateAnalysisInput['options'];
  }): Promise<TopicChunkBoundary[]> {
    const adapter = this.resolveAdapter(input.options.provider);
    const prompt = buildTopicChunkingPrompt({
      transcriptSegments: input.transcriptSegments,
      targetLanguage: input.targetLanguage,
    });
    const rawText = await adapter.generateJson(
      prompt,
      input.options,
      TOPIC_CHUNKING_SCHEMA,
    );
    const payload = this.parseObject(rawText, 'LLM_TOPIC_CHUNKS_INVALID_JSON');
    const topicChunks = (payload as { topicChunks?: unknown }).topicChunks;

    if (!Array.isArray(topicChunks) || topicChunks.length === 0) {
      throw new AppException(
        502,
        'LLM_TOPIC_CHUNKS_EMPTY',
        'No topic chunks returned',
      );
    }

    return topicChunks.map((chunk, index) => {
      if (!chunk || typeof chunk !== 'object') {
        throw new AppException(
          502,
          'LLM_TOPIC_CHUNKS_INVALID_JSON',
          `Invalid topic chunk at index ${index}`,
        );
      }
      const value = chunk as Record<string, unknown>;
      if (
        typeof value.startSegmentId !== 'string' ||
        typeof value.endSegmentId !== 'string' ||
        typeof value.title !== 'string' ||
        typeof value.summary !== 'string' ||
        !['high', 'medium', 'low', 'off_topic'].includes(
          String(value.signalLevel),
        )
      ) {
        throw new AppException(
          502,
          'LLM_TOPIC_CHUNKS_INVALID_JSON',
          `Invalid topic chunk fields at index ${index}`,
        );
      }

      return {
        startSegmentId: value.startSegmentId.trim(),
        endSegmentId: value.endSegmentId.trim(),
        title: value.title.trim(),
        summary: value.summary.trim(),
        signalLevel: value.signalLevel as TopicChunkBoundary['signalLevel'],
      };
    });
  }

  async generateCandidateClippings(input: {
    chunkTitle: string;
    chunkSummary: string;
    chunkSegments: string;
    targetLanguage: string;
    options: GenerateAnalysisInput['options'];
  }): Promise<CandidateClippingOutput[]> {
    const adapter = this.resolveAdapter(input.options.provider);
    const prompt = buildCandidateClippingPrompt({
      chunkTitle: input.chunkTitle,
      chunkSummary: input.chunkSummary,
      chunkSegments: input.chunkSegments,
      targetLanguage: input.targetLanguage,
    });
    const rawText = await adapter.generateJson(
      prompt,
      input.options,
      CANDIDATE_CLIPPING_SCHEMA,
    );
    const payload = this.parseObject(rawText, 'LLM_CLIPPINGS_INVALID_JSON');
    const candidateClippings = (payload as { candidateClippings?: unknown })
      .candidateClippings;

    if (!Array.isArray(candidateClippings)) {
      throw new AppException(
        502,
        'LLM_CLIPPINGS_INVALID_JSON',
        'Invalid candidate clipping list',
      );
    }

    const chunkSegmentIds = this.extractPromptSegmentIds(input.chunkSegments);

    return candidateClippings.map((candidate, index) =>
      this.parseCandidateClipping(candidate, index, chunkSegmentIds),
    );
  }

  async analyzeCategories(input: GenerateAnalysisInput): Promise<AnalysisWithLlmSettings> {
    const adapter = this.resolveAdapter(input.options.provider);

    const prompt = buildCategoryExtractionPrompt({
      transcriptText: input.transcriptText,
      transcriptType: input.transcriptType,
      targetLanguage: input.targetLanguage,
      youtubeUrl: input.youtubeUrl,
    });

    const rawText = await adapter.generateJson(prompt, input.options);
    const payload = this.parseAnalysis(rawText);

    if (payload.sourceType !== input.transcriptType) {
      throw new AppException(
        502,
        'LLM_ANALYZE_SOURCE_MISMATCH',
        'Model returned invalid sourceType',
      );
    }

    if (input.transcriptType === 'youtube') {
      this.resolveYoutubeSources(
        payload,
        input.youtubeUrl ?? '',
        input.segmentIndex ?? [],
      );
    }

    return {
      ...payload,
      llm: input.options,
    };
  }

  async summarizeTranscript(input: GenerateSummaryInput): Promise<SummaryWithLlmSettings> {
    const adapter = this.resolveAdapter(input.options.provider);

    const prompt = buildTranscriptSummaryPrompt({
      transcriptText: input.transcriptText,
      transcriptType: input.transcriptType,
      targetLanguage: input.targetLanguage,
    });
    const rawText = await adapter.generateJson(prompt, input.options);
    const payload = this.parseSummary(rawText);

    if (input.transcriptType === 'youtube') {
      payload.timestamps = this.resolveSummaryYoutubeTimestamps(
        payload,
        input.youtubeUrl ?? '',
        input.segmentIndex ?? [],
      );
    }

    return {
      ...payload,
      llm: input.options,
      ...(input.includeRawText ? { rawText } : {}),
    };
  }

  private parseAnalysis(rawText: string): CategoryAnalysis {
    const normalized = rawText
      .trim()
      .replace(/^```json\s*/i, '')
      .replace(/^```\s*/i, '')
      .replace(/\s*```$/, '')
      .trim();

    if (!normalized) {
      throw new AppException(502, 'LLM_ANALYZE_EMPTY', 'Model returned empty output');
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(normalized);
    } catch {
      throw new AppException(
        502,
        'LLM_ANALYZE_INVALID_JSON',
        'Model returned invalid JSON',
      );
    }

    if (!parsed || typeof parsed !== 'object') {
      throw new AppException(
        502,
        'LLM_ANALYZE_INVALID_JSON',
        'Model returned invalid analysis payload',
      );
    }

    const payload = parsed as Partial<CategoryAnalysis>;
    if (payload.sourceType !== 'youtube' && payload.sourceType !== 'manual') {
      throw new AppException(
        502,
        'LLM_ANALYZE_INVALID_JSON',
        'Model returned invalid sourceType',
      );
    }

    if (!Array.isArray(payload.categories) || payload.categories.length === 0) {
      throw new AppException(502, 'LLM_ANALYZE_EMPTY', 'No categories returned');
    }

    for (const [categoryIndex, category] of payload.categories.entries()) {
      if (!category || typeof category.title !== 'string') {
        throw new AppException(
          502,
          'LLM_ANALYZE_INVALID_JSON',
          `Model returned invalid category at index ${categoryIndex}`,
        );
      }

      if (!Array.isArray(category.keywords) || category.keywords.length === 0) {
        throw new AppException(
          502,
          'LLM_ANALYZE_INVALID_JSON',
          `Model returned invalid keywords at category index ${categoryIndex}`,
        );
      }

      for (const keyword of category.keywords) {
        this.assertKeyword(keyword);
      }
    }

    return payload as CategoryAnalysis;
  }

  private parseObject(rawText: string, code: string): Record<string, unknown> {
    const normalized = rawText
      .trim()
      .replace(/^```json\s*/i, '')
      .replace(/^```\s*/i, '')
      .replace(/\s*```$/, '')
      .trim();

    if (!normalized) {
      throw new AppException(502, code, 'Model returned empty output');
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(normalized);
    } catch {
      throw new AppException(502, code, 'Model returned invalid JSON');
    }

    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new AppException(502, code, 'Model returned invalid JSON object');
    }

    return parsed as Record<string, unknown>;
  }

  private parseCandidateClipping(
    candidate: unknown,
    index: number,
    chunkSegmentIds: string[],
  ): CandidateClippingOutput {
    if (!candidate || typeof candidate !== 'object') {
      throw new AppException(
        502,
        'LLM_CLIPPINGS_INVALID_JSON',
        `Invalid candidate clipping at index ${index}`,
      );
    }

    const value = candidate as Record<string, unknown>;
    const sourceRefs = value.sourceRefs;
    if (
      typeof value.kind !== 'string' ||
      typeof value.title !== 'string' ||
      typeof value.text !== 'string' ||
      typeof value.brief !== 'string' ||
      typeof value.simpleExplanation !== 'string' ||
      typeof value.contextualExplanation !== 'string' ||
      typeof value.detailedExplanation !== 'string' ||
      !['high', 'medium', 'low'].includes(String(value.signalLevel)) ||
      !Array.isArray(sourceRefs) ||
      sourceRefs.length === 0
    ) {
      throw new AppException(
        502,
        'LLM_CLIPPINGS_INVALID_JSON',
        `Invalid candidate clipping fields at index ${index}`,
      );
    }

    const title = value.title.trim();
    const brief = value.brief.trim();
    const simpleExplanation = value.simpleExplanation.trim();
    const contextualExplanation = value.contextualExplanation.trim();
    const detailedExplanation = value.detailedExplanation.trim();
    this.assertExplanationLadder({
      term: title,
      brief,
      simpleExplanation,
      contextualExplanation,
      detailedExplanation,
      code: 'LLM_CLIPPINGS_INVALID_JSON',
    });

    const segmentOrder = new Map(
      chunkSegmentIds.map((segmentId, segmentIndex) => [segmentId, segmentIndex]),
    );

    return {
      kind: value.kind.trim(),
      title,
      text: value.text.trim(),
      brief,
      simpleExplanation,
      contextualExplanation,
      detailedExplanation,
      signalLevel: value.signalLevel as CandidateClippingOutput['signalLevel'],
      sourceRefs: sourceRefs.map((sourceRef, sourceIndex) => {
        if (!sourceRef || typeof sourceRef !== 'object') {
          throw new AppException(
            502,
            'LLM_CLIPPINGS_INVALID_JSON',
            `Invalid source ref at candidate ${index}, source ${sourceIndex}`,
          );
        }
        const ref = sourceRef as Record<string, unknown>;
        if (
          typeof ref.startSegmentId !== 'string' ||
          typeof ref.endSegmentId !== 'string' ||
          typeof ref.timestamp !== 'string' ||
          typeof ref.text !== 'string'
        ) {
          throw new AppException(
            502,
            'LLM_CLIPPINGS_INVALID_JSON',
            `Invalid source ref fields at candidate ${index}, source ${sourceIndex}`,
          );
        }

        const startSegmentId = ref.startSegmentId.trim();
        const endSegmentId = ref.endSegmentId.trim();
        const startIndex = segmentOrder.get(startSegmentId);
        const endIndex = segmentOrder.get(endSegmentId);
        if (
          startIndex === undefined ||
          endIndex === undefined ||
          startIndex > endIndex
        ) {
          throw new AppException(
            502,
            'LLM_CLIPPINGS_INVALID_SOURCE_REF',
            `Source ref outside topic chunk at candidate ${index}, source ${sourceIndex}`,
          );
        }

        return {
          startSegmentId,
          endSegmentId,
          timestamp: ref.timestamp.trim(),
          text: ref.text.trim(),
        };
      }),
    };
  }

  private extractPromptSegmentIds(chunkSegments: string): string[] {
    return chunkSegments
      .split('\n')
      .map((line) => line.match(/^\s*([^|\s]+)\s*\|/)?.[1]?.trim())
      .filter((segmentId): segmentId is string => Boolean(segmentId));
  }

  private assertExplanationLadder(input: {
    term: string;
    brief: string;
    simpleExplanation: string;
    contextualExplanation: string;
    detailedExplanation: string;
    code: string;
  }) {
    const values = [
      input.term,
      input.brief,
      input.simpleExplanation,
      input.contextualExplanation,
      input.detailedExplanation,
    ];
    if (values.some((value) => !value.trim())) {
      throw new AppException(502, input.code, 'Explanation ladder fields must not be empty');
    }

    if (input.term.length > 60 || /[.!?]\s*$/.test(input.term)) {
      throw new AppException(502, input.code, 'Keyword term must be a short label');
    }

    const normalizedLevels = [
      input.simpleExplanation,
      input.contextualExplanation,
      input.detailedExplanation,
    ].map((value) => this.normalizeExplanation(value));
    if (new Set(normalizedLevels).size !== normalizedLevels.length) {
      throw new AppException(
        502,
        input.code,
        'Explanation ladder levels must not be duplicates',
      );
    }

    const briefWordCount = this.wordCount(input.brief);
    if (
      briefWordCount < 5 ||
      briefWordCount > 10 ||
      input.brief.length >= input.simpleExplanation.length
    ) {
      throw new AppException(
        502,
        input.code,
        'Keyword brief must be shorter than the simple explanation',
      );
    }

    const simpleSentenceCount = this.sentenceCount(input.simpleExplanation);
    const contextualSentenceCount = this.sentenceCount(input.contextualExplanation);
    const detailedSentenceCount = this.sentenceCount(input.detailedExplanation);

    if (
      simpleSentenceCount !== 1 ||
      input.simpleExplanation.length >= input.contextualExplanation.length
    ) {
      throw new AppException(
        502,
        input.code,
        'Simple explanation must be shorter and simpler than contextual explanation',
      );
    }

    if (contextualSentenceCount < 2 || contextualSentenceCount > 3) {
      throw new AppException(
        502,
        input.code,
        'Contextual explanation must be 2-3 sentences',
      );
    }

    if (
      detailedSentenceCount < 3 ||
      detailedSentenceCount > 5 ||
      input.detailedExplanation.length <= input.contextualExplanation.length
    ) {
      throw new AppException(
        502,
        input.code,
        'Detailed explanation must add more detail than contextual explanation',
      );
    }
  }

  private normalizeExplanation(value: string): string {
    return value.toLowerCase().replace(/\s+/g, ' ').replace(/[.?!]+$/g, '').trim();
  }

  private wordCount(value: string): number {
    return value.trim().split(/\s+/).filter(Boolean).length;
  }

  private sentenceCount(value: string): number {
    return value.split(/[.!?]+/).filter((part) => part.trim()).length;
  }

  private resolveAdapter(provider: GenerateAnalysisInput['options']['provider']) {
    const adapter = this.adapters.find((candidate) => candidate.provider === provider);
    if (!adapter) {
      throw new AppException(
        500,
        'LLM_PROVIDER_NOT_SUPPORTED',
        `LLM provider '${provider}' is not supported`,
      );
    }

    return adapter;
  }

  private parseSummary(rawText: string): TranscriptSummary {
    const normalized = rawText
      .trim()
      .replace(/^```json\s*/i, '')
      .replace(/^```\s*/i, '')
      .replace(/\s*```$/, '')
      .trim();

    if (!normalized) {
      throw new AppException(502, 'LLM_SUMMARY_EMPTY', 'Model returned empty output');
    }

    let parsed: unknown;
    try {
      parsed = JSON.parse(normalized);
    } catch {
      throw new AppException(
        502,
        'LLM_SUMMARY_INVALID_JSON',
        'Model returned invalid JSON',
      );
    }

    if (!parsed || typeof parsed !== 'object') {
      throw new AppException(
        502,
        'LLM_SUMMARY_INVALID_JSON',
        'Model returned invalid summary payload',
      );
    }

    const payload = parsed as {
      summary?: unknown;
      timestamps?: unknown;
    };

    if (typeof payload.summary !== 'string' || !payload.summary.trim()) {
      throw new AppException(
        502,
        'LLM_SUMMARY_INVALID_JSON',
        'Model returned invalid summary',
      );
    }

    if (!Array.isArray(payload.timestamps)) {
      throw new AppException(
        502,
        'LLM_SUMMARY_INVALID_JSON',
        'Model returned invalid timestamps',
      );
    }

    const timestamps = payload.timestamps.map((item) => {
      if (!item || typeof item !== 'object') {
        throw new AppException(
          502,
          'LLM_SUMMARY_INVALID_JSON',
          'Model returned invalid timestamp item',
        );
      }

      const moment = item as Record<string, unknown>;
      if (
        typeof moment.time !== 'string' ||
        typeof moment.title !== 'string' ||
        typeof moment.summary !== 'string'
      ) {
        throw new AppException(
          502,
          'LLM_SUMMARY_INVALID_JSON',
          'Model returned invalid timestamp fields',
        );
      }

      return {
        time: moment.time.trim(),
        seconds: this.timestampToSeconds(moment.time.trim()),
        title: moment.title.trim(),
        summary: moment.summary.trim(),
      };
    });

    return {
      summary: payload.summary.trim(),
      timestamps,
    };
  }

  private assertKeyword(keyword: CategoryKeyword) {
    const source = keyword?.source;
    if (
      !keyword ||
      typeof keyword.term !== 'string' ||
      typeof keyword.brief !== 'string' ||
      typeof keyword.level1 !== 'string' ||
      typeof keyword.level2 !== 'string' ||
      typeof keyword.level3 !== 'string' ||
      !source ||
      (source.type !== 'youtube' && source.type !== 'manual') ||
      typeof source.ref !== 'string' ||
      !source.ref.trim()
    ) {
      throw new AppException(
        502,
        'LLM_ANALYZE_INVALID_JSON',
        'Model returned invalid keyword payload',
      );
    }

    this.assertExplanationLadder({
      term: keyword.term.trim(),
      brief: keyword.brief.trim(),
      simpleExplanation: keyword.level1.trim(),
      contextualExplanation: keyword.level2.trim(),
      detailedExplanation: keyword.level3.trim(),
      code: 'LLM_ANALYZE_INVALID_JSON',
    });
  }

  private resolveYoutubeSources(
    payload: CategoryAnalysis,
    youtubeUrl: string,
    segmentIndex: SegmentIndexEntry[],
  ) {
    if (!segmentIndex.length) {
      throw new AppException(
        502,
        'LLM_INVALID_SOURCE_REF',
        'No transcript segments available for citation',
      );
    }

    const indexByTimestamp = new Map<string, SegmentIndexEntry>();
    for (const segment of segmentIndex) {
      indexByTimestamp.set(formatTimestamp(segment.startSec), segment);
    }

    for (const [categoryIndex, category] of payload.categories.entries()) {
      for (const [keywordIndex, keyword] of category.keywords.entries()) {
        const source = keyword.source;
        if (source.type !== 'youtube') {
          this.throwInvalidYoutubeSourceRef(
            "YouTube keyword source.type must be 'youtube'",
            { categoryIndex, keywordIndex, reason: 'invalid_source_type' },
          );
        }

        const rawRef = source.ref.trim();
        if (!/^\d{1,2}:\d{2}(:\d{2})?$/.test(rawRef)) {
          this.throwInvalidYoutubeSourceRef(
            'YouTube source.ref must be a timestamp like 13:38',
            { categoryIndex, keywordIndex, rawRef, reason: 'non_timestamp_source_ref' },
          );
        }

        const segment = indexByTimestamp.get(rawRef);
        if (!segment) {
          this.throwInvalidYoutubeSourceRef(
            `Model returned unknown source timestamp: ${rawRef}`,
            {
              categoryIndex,
              keywordIndex,
              rawRef,
              knownSegmentCount: indexByTimestamp.size,
              reason: 'unknown_timestamp',
            },
          );
        }

        keyword.source.ref = this.toYoutubeTimestampUrl(youtubeUrl, segment.startSec);
      }
    }
  }

  private toYoutubeTimestampUrl(youtubeUrl: string, startSec: number): string {
    const url = new URL(youtubeUrl);
    url.searchParams.set('t', `${Math.max(0, Math.floor(startSec))}s`);
    return url.toString();
  }

  private resolveSummaryYoutubeTimestamps(
    payload: TranscriptSummary,
    youtubeUrl: string,
    segmentIndex: SegmentIndexEntry[],
  ) {
    if (!segmentIndex.length) {
      throw new AppException(
        502,
        'LLM_INVALID_SOURCE_REF',
        'No transcript segments available for timestamp validation',
      );
    }

    const indexByTimestamp = new Map<string, SegmentIndexEntry>();
    for (const segment of segmentIndex) {
      indexByTimestamp.set(formatTimestamp(segment.startSec), segment);
    }

    return payload.timestamps.map((moment) => {
      const segment = indexByTimestamp.get(moment.time);
      if (!segment) {
        throw new AppException(
          502,
          'LLM_INVALID_SOURCE_REF',
          `Model returned unknown summary timestamp: ${moment.time}`,
        );
      }

      return {
        ...moment,
        seconds: Math.max(0, Math.floor(segment.startSec)),
        url: this.toYoutubeTimestampUrl(youtubeUrl, segment.startSec),
      };
    });
  }

  private timestampToSeconds(value: string): number {
    if (!/^\d{1,2}:\d{2}(:\d{2})?$/.test(value)) {
      throw new AppException(
        502,
        'LLM_SUMMARY_INVALID_JSON',
        'Model returned invalid timestamp format',
      );
    }

    const parts = value.split(':').map((part) => Number(part));
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    }

    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }

  private throwInvalidYoutubeSourceRef(message: string, details: Record<string, unknown>): never {
    this.logger.error({ event: 'llm.invalid_youtube_source_ref', ...details });
    throw new AppException(502, 'LLM_INVALID_SOURCE_REF', message);
  }
}
