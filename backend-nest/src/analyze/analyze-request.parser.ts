import { Injectable } from '@nestjs/common';

import { AppException } from '../common/app.exception';
import { AnalyzeSource } from './analyze.types';

const TARGET_LANGUAGE_REGEX =
  /^[a-zA-Z]{2,3}(?:-[a-zA-Z]{4})?(?:-[a-zA-Z]{2}|\d{3})?$/;

@Injectable()
export class AnalyzeRequestParser {
  private readonly allowAnalyzeLlmOverrides =
    process.env.ALLOW_ANALYZE_LLM_OVERRIDES === 'true';

  parse(body: unknown): AnalyzeSource {
    if (!body || typeof body !== 'object' || Array.isArray(body)) {
      throw new AppException(400, 'INVALID_REQUEST', 'Request body must be a JSON object');
    }

    const input = body as Record<string, unknown>;
    const type = input.type;
    if (type !== 'youtube' && type !== 'manual') {
      throw new AppException(400, 'INVALID_TYPE', "type must be either 'youtube' or 'manual'");
    }

    const title = this.optionalTitle(input.title);
    const targetLanguage = this.targetLanguage(input.targetLanguage);
    const llmOverrides = this.allowAnalyzeLlmOverrides
      ? {
          provider: input.provider,
          model: input.model,
          temperature: input.temperature,
          maxOutputTokens: input.maxOutputTokens,
        }
      : {};
    const llmOverrideKeys = this.allowAnalyzeLlmOverrides
      ? ['provider', 'model', 'temperature', 'maxOutputTokens']
      : [];

    if (type === 'youtube') {
      this.assertNoUnknownKeys(input, [
        'type',
        'youtubeUrl',
        'title',
        'targetLanguage',
        ...llmOverrideKeys,
      ]);

      const youtubeUrl = this.youtubeUrl(input.youtubeUrl);
      return {
        type,
        youtubeUrl,
        targetLanguage,
        ...(title ? { title } : {}),
        ...llmOverrides,
      };
    }

    this.assertNoUnknownKeys(input, [
      'type',
      'text',
      'title',
      'targetLanguage',
      ...llmOverrideKeys,
    ]);

    const text = this.text(input.text);
    return {
      type,
      text,
      targetLanguage,
      ...(title ? { title } : {}),
      ...llmOverrides,
    };
  }

  assertTranscriptText(value: unknown): string {
    if (typeof value !== 'string') {
      throw new AppException(502, 'INVALID_TRANSCRIPT', 'Transcript text is invalid');
    }

    const trimmed = value.trim();
    if (!trimmed) {
      throw new AppException(502, 'EMPTY_TRANSCRIPT', 'Transcript is empty or unavailable');
    }

    if (trimmed.length < 80) {
      throw new AppException(502, 'SHORT_TRANSCRIPT', 'Transcript is too short for analysis');
    }

    return trimmed;
  }

  private assertNoUnknownKeys(input: Record<string, unknown>, allowed: string[]) {
    const unknownKeys = Object.keys(input).filter((key) => !allowed.includes(key));
    if (unknownKeys.length) {
      throw new AppException(
        400,
        'INVALID_REQUEST',
        `Unsupported request field: ${unknownKeys[0]}`,
      );
    }
  }

  private youtubeUrl(value: unknown): string {
    if (typeof value !== 'string' || !value.trim()) {
      throw new AppException(
        400,
        'INVALID_YOUTUBE_URL',
        'youtubeUrl must be a non-empty string',
      );
    }
    return value.trim();
  }

  private text(value: unknown): string {
    if (typeof value !== 'string' || !value.trim()) {
      throw new AppException(400, 'INVALID_TEXT', 'text must be a non-empty string');
    }
    return value.trim();
  }

  private optionalTitle(value: unknown): string | undefined {
    if (value === undefined) {
      return undefined;
    }

    if (typeof value !== 'string' || !value.trim()) {
      throw new AppException(
        400,
        'INVALID_TITLE',
        'title must be a non-empty string when provided',
      );
    }

    return value.trim();
  }

  private targetLanguage(value: unknown): string {
    if (value === undefined) {
      return 'en';
    }

    if (typeof value !== 'string' || !value.trim()) {
      throw new AppException(
        400,
        'INVALID_TARGET_LANGUAGE',
        'targetLanguage must be a non-empty BCP-47 language code',
      );
    }

    const trimmed = value.trim();
    if (!TARGET_LANGUAGE_REGEX.test(trimmed)) {
      throw new AppException(
        400,
        'INVALID_TARGET_LANGUAGE',
        'targetLanguage must be a valid BCP-47 language code',
      );
    }

    return trimmed
      .split('-')
      .map((part, index) => {
        if (index === 0) {
          return part.toLowerCase();
        }
        if (part.length === 4) {
          return `${part[0].toUpperCase()}${part.slice(1).toLowerCase()}`;
        }
        return part.length === 2 ? part.toUpperCase() : part;
      })
      .join('-');
  }
}
