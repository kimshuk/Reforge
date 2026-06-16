import { AnalyzeRequestParser } from './analyze-request.parser';

describe('AnalyzeRequestParser', () => {
  beforeEach(() => {
    delete process.env.ALLOW_ANALYZE_LLM_OVERRIDES;
  });

  it('rejects public provider overrides by default', () => {
    const parser = new AnalyzeRequestParser();

    expect(
      () => parser.parse({
        type: 'manual',
        text: 'A transcript with enough text to be accepted before the later length check.',
        targetLanguage: 'ko-kr',
        provider: 'gemini',
        model: 'gemini-1.5-pro',
        temperature: 0.4,
        maxOutputTokens: 2048,
      }),
    ).toThrow('Unsupported request field: provider');
  });

  it('parses manual requests without provider overrides', () => {
    const parser = new AnalyzeRequestParser();

    expect(
      parser.parse({
        type: 'manual',
        text: 'A transcript with enough text to be accepted before the later length check.',
        targetLanguage: 'ko-kr',
      }),
    ).toEqual({
      type: 'manual',
      text: 'A transcript with enough text to be accepted before the later length check.',
      targetLanguage: 'ko-KR',
    });
  });

  it('rejects unknown fields', () => {
    const parser = new AnalyzeRequestParser();

    expect(() =>
      parser.parse({
        type: 'manual',
        text: 'hello',
        arbitrary: true,
      }),
    ).toThrow('Unsupported request field: arbitrary');
  });
});
