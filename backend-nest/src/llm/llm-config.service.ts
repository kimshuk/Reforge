import { Injectable } from '@nestjs/common';

import { AppException } from '../common/app.exception';
import { LlmOptions, LlmProvider, LlmRequestOverrides } from './llm.types';

const PROVIDERS: LlmProvider[] = ['openai', 'gemini', 'claude'];
const DEFAULT_MODELS: Record<LlmProvider, string> = {
  openai: 'gpt-4o-mini',
  gemini: 'gemini-1.5-flash',
  claude: 'claude-3-5-haiku-latest',
};

@Injectable()
export class LlmConfigService {
  resolve(overrides: LlmRequestOverrides = {}): LlmOptions {
    const provider = this.resolveProvider(overrides.provider);
    const model = this.resolveModel(overrides.model, provider);
    const temperature = this.resolveTemperature(overrides.temperature);
    const maxOutputTokens = this.resolveMaxOutputTokens(overrides.maxOutputTokens);

    return {
      provider,
      model,
      temperature,
      ...(maxOutputTokens ? { maxOutputTokens } : {}),
    };
  }

  apiKey(provider: LlmProvider): string {
    const envKey =
      provider === 'openai'
        ? 'OPENAI_API_KEY'
        : provider === 'gemini'
          ? 'GEMINI_API_KEY'
          : 'ANTHROPIC_API_KEY';
    const key = process.env[envKey]?.trim();

    if (!key) {
      throw new AppException(
        500,
        'LLM_PROVIDER_NOT_CONFIGURED',
        `${envKey} is required for provider '${provider}'`,
      );
    }

    return key;
  }

  private resolveProvider(input: unknown): LlmProvider {
    const value =
      input === undefined
        ? (process.env.LLM_PROVIDER ?? 'openai')
        : input;

    if (typeof value !== 'string') {
      throw new AppException(
        400,
        'INVALID_LLM_PROVIDER',
        'provider must be openai, gemini, or claude',
      );
    }

    const normalized = value.trim().toLowerCase();
    if (!PROVIDERS.includes(normalized as LlmProvider)) {
      throw new AppException(
        400,
        'INVALID_LLM_PROVIDER',
        'provider must be openai, gemini, or claude',
      );
    }

    return normalized as LlmProvider;
  }

  private resolveModel(input: unknown, provider: LlmProvider): string {
    const value =
      input === undefined
        ? (process.env.LLM_MODEL ?? DEFAULT_MODELS[provider])
        : input;

    if (typeof value !== 'string' || !value.trim()) {
      throw new AppException(400, 'INVALID_LLM_MODEL', 'model must be a non-empty string');
    }

    return value.trim();
  }

  private resolveTemperature(input: unknown): number {
    const value =
      input === undefined
        ? (process.env.LLM_TEMPERATURE ?? '0.2')
        : input;
    const parsed = Number(value);

    if (!Number.isFinite(parsed) || parsed < 0 || parsed > 2) {
      throw new AppException(
        400,
        'INVALID_LLM_TEMPERATURE',
        'temperature must be a number between 0 and 2',
      );
    }

    return parsed;
  }

  private resolveMaxOutputTokens(input: unknown): number | undefined {
    const value =
      input === undefined ? process.env.LLM_MAX_OUTPUT_TOKENS : input;

    if (value === undefined || value === null || value === '') {
      return undefined;
    }

    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed < 256 || parsed > 20000) {
      throw new AppException(
        400,
        'INVALID_LLM_MAX_OUTPUT_TOKENS',
        'maxOutputTokens must be an integer between 256 and 20000',
      );
    }

    return parsed;
  }
}
