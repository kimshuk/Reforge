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
export class GeminiAdapter implements LlmProviderAdapter {
  readonly provider = 'gemini' as const;

  constructor(private readonly config: LlmConfigService) {}

  async generateJson(
    prompt: ProviderPrompt,
    options: LlmOptions,
    _schema?: JsonSchemaFormat,
  ): Promise<string> {
    const key = this.config.apiKey('gemini');
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(
      options.model,
    )}:generateContent?key=${encodeURIComponent(key)}`;

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        systemInstruction: {
          parts: [{ text: prompt.system }],
        },
        contents: [
          {
            role: 'user',
            parts: [{ text: prompt.user }],
          },
        ],
        generationConfig: {
          temperature: options.temperature,
          ...(options.maxOutputTokens
            ? { maxOutputTokens: options.maxOutputTokens }
            : {}),
          responseMimeType: 'application/json',
        },
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
          : 'Gemini request failed';
      throw new AppException(502, 'LLM_REQUEST_FAILED', message);
    }

    const candidates = payload?.candidates;
    if (!Array.isArray(candidates)) {
      throw new AppException(502, 'LLM_EMPTY_OUTPUT', 'Gemini returned empty output');
    }

    const first = candidates[0] as { content?: { parts?: Array<{ text?: string }> } };
    const text = first?.content?.parts
      ?.map((part) => part.text ?? '')
      .join('')
      .trim();

    if (!text) {
      throw new AppException(502, 'LLM_EMPTY_OUTPUT', 'Gemini returned empty output');
    }

    return text;
  }
}
