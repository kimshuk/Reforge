import { Injectable } from '@nestjs/common';

import { AppException } from '../../common/app.exception';
import { CATEGORY_EXTRACTION_SCHEMA } from '../category-extraction.prompt';
import { LlmConfigService } from '../llm-config.service';
import {
  JsonSchemaFormat,
  LlmOptions,
  LlmProviderAdapter,
  ProviderPrompt,
} from '../llm.types';

@Injectable()
export class OpenAiAdapter implements LlmProviderAdapter {
  readonly provider = 'openai' as const;

  constructor(private readonly config: LlmConfigService) {}

  async generateJson(
    prompt: ProviderPrompt,
    options: LlmOptions,
    schema: JsonSchemaFormat = CATEGORY_EXTRACTION_SCHEMA,
  ): Promise<string> {
    const response = await fetch('https://api.openai.com/v1/responses', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${this.config.apiKey('openai')}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: options.model,
        temperature: options.temperature,
        ...(options.maxOutputTokens
          ? { max_output_tokens: options.maxOutputTokens }
          : {}),
        input: [
          { role: 'system', content: prompt.system },
          { role: 'user', content: prompt.user },
        ],
        text: {
          format: {
            type: 'json_schema',
            name: schema.name,
            schema: schema.schema,
            strict: schema.strict,
          },
        },
      }),
    });

    const payload = (await response.json().catch(() => null)) as Record<
      string,
      unknown
    > | null;

    if (!response.ok) {
      throw this.toProviderError(response.status, payload);
    }

    if (payload?.status === 'incomplete') {
      throw new AppException(
        502,
        'LLM_RESPONSE_INCOMPLETE',
        'OpenAI returned an incomplete response',
      );
    }

    if (payload?.status === 'failed') {
      throw new AppException(502, 'LLM_REQUEST_FAILED', 'OpenAI response failed');
    }

    const outputText = this.extractOutputText(payload);
    if (!outputText) {
      throw new AppException(502, 'LLM_EMPTY_OUTPUT', 'OpenAI returned empty output');
    }

    return outputText;
  }

  private extractOutputText(payload: Record<string, unknown> | null): string {
    if (typeof payload?.output_text === 'string') {
      return payload.output_text;
    }

    const output = payload?.output;
    if (!Array.isArray(output)) {
      return '';
    }

    const chunks: string[] = [];
    for (const item of output) {
      if (!item || typeof item !== 'object') {
        continue;
      }

      const content = (item as { content?: unknown }).content;
      if (!Array.isArray(content)) {
        continue;
      }

      for (const part of content) {
        if (part && typeof part === 'object') {
          const text = (part as { text?: unknown }).text;
          if (typeof text === 'string') {
            chunks.push(text);
          }
        }
      }
    }

    return chunks.join('');
  }

  private toProviderError(status: number, payload: Record<string, unknown> | null) {
    const error = payload?.error as Record<string, unknown> | undefined;
    const apiCode = typeof error?.code === 'string' ? error.code : null;
    const apiMessage =
      typeof error?.message === 'string'
        ? error.message
        : 'OpenAI request failed';

    if (status === 401 || apiCode === 'invalid_api_key') {
      return new AppException(502, 'LLM_AUTH_ERROR', apiMessage);
    }

    if (
      status === 429 ||
      apiCode === 'insufficient_quota' ||
      apiCode === 'rate_limit_exceeded'
    ) {
      return new AppException(502, 'LLM_QUOTA_OR_RATE_LIMIT', apiMessage);
    }

    if (apiCode === 'context_length_exceeded') {
      return new AppException(502, 'LLM_CONTEXT_LENGTH_EXCEEDED', apiMessage);
    }

    return new AppException(502, 'LLM_REQUEST_FAILED', apiMessage);
  }
}
