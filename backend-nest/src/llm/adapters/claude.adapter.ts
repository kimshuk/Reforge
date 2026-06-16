import { Injectable } from '@nestjs/common';

import { AppException } from '../../common/app.exception';
import { LlmConfigService } from '../llm-config.service';
import {
  JsonSchemaFormat,
  LlmOptions,
  LlmProviderAdapter,
  ProviderPrompt,
} from '../llm.types';

@Injectable()
export class ClaudeAdapter implements LlmProviderAdapter {
  readonly provider = 'claude' as const;

  constructor(private readonly config: LlmConfigService) {}

  async generateJson(
    prompt: ProviderPrompt,
    options: LlmOptions,
    _schema?: JsonSchemaFormat,
  ): Promise<string> {
    const response = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': this.config.apiKey('claude'),
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: options.model,
        temperature: options.temperature,
        max_tokens: options.maxOutputTokens ?? 3000,
        system: prompt.system,
        messages: [{ role: 'user', content: prompt.user }],
      }),
    });

    const payload = (await response.json().catch(() => null)) as Record<
      string,
      unknown
    > | null;

    if (!response.ok) {
      const error = payload?.error as Record<string, unknown> | undefined;
      const message =
        typeof error?.message === 'string'
          ? error.message
          : 'Claude request failed';
      throw new AppException(502, 'LLM_REQUEST_FAILED', message);
    }

    const content = payload?.content;
    if (!Array.isArray(content)) {
      throw new AppException(502, 'LLM_EMPTY_OUTPUT', 'Claude returned empty output');
    }

    const text = content
      .map((part) =>
        part && typeof part === 'object' && typeof (part as { text?: unknown }).text === 'string'
          ? (part as { text: string }).text
          : '',
      )
      .join('')
      .trim();

    if (!text) {
      throw new AppException(502, 'LLM_EMPTY_OUTPUT', 'Claude returned empty output');
    }

    return text;
  }
}
