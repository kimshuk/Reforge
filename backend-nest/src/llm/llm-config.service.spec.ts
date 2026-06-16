import { LlmConfigService } from './llm-config.service';

describe('LlmConfigService', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    process.env = { ...originalEnv };
    delete process.env.LLM_PROVIDER;
    delete process.env.LLM_MODEL;
    delete process.env.LLM_TEMPERATURE;
    delete process.env.LLM_MAX_OUTPUT_TOKENS;
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('uses OpenAI defaults', () => {
    expect(new LlmConfigService().resolve()).toEqual({
      provider: 'openai',
      model: 'gpt-4o-mini',
      temperature: 0.2,
    });
  });

  it('allows per-request provider and settings overrides', () => {
    expect(
      new LlmConfigService().resolve({
        provider: 'claude',
        model: 'claude-3-5-sonnet-latest',
        temperature: 0.7,
        maxOutputTokens: 4096,
      }),
    ).toEqual({
      provider: 'claude',
      model: 'claude-3-5-sonnet-latest',
      temperature: 0.7,
      maxOutputTokens: 4096,
    });
  });

  it('rejects unsupported providers', () => {
    expect(() => new LlmConfigService().resolve({ provider: 'local' })).toThrow(
      'provider must be openai, gemini, or claude',
    );
  });
});
