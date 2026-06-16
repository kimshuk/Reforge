import { ProviderPrompt } from './llm.types';

export const CANDIDATE_CLIPPING_SCHEMA = {
  name: 'candidate_clipping',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['candidateClippings'],
    properties: {
      candidateClippings: {
        type: 'array',
        items: {
          type: 'object',
          additionalProperties: false,
          required: [
            'kind',
            'title',
            'text',
            'brief',
            'level1',
            'level2',
            'level3',
            'signalLevel',
            'sourceRefs',
          ],
          properties: {
            kind: {
              type: 'string',
              enum: [
                'topic',
                'claim',
                'mechanism',
                'risk',
                'trend',
                'entity',
                'example',
                'question',
                'contradiction',
              ],
            },
            title: { type: 'string', minLength: 3, maxLength: 80 },
            text: { type: 'string', minLength: 3, maxLength: 500 },
            brief: { type: 'string', minLength: 3, maxLength: 120 },
            level1: { type: 'string', minLength: 3, maxLength: 160 },
            level2: { type: 'string', minLength: 3, maxLength: 320 },
            level3: { type: 'string', minLength: 3, maxLength: 500 },
            signalLevel: {
              type: 'string',
              enum: ['high', 'medium', 'low'],
            },
            sourceRefs: {
              type: 'array',
              minItems: 1,
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['startSegmentId', 'endSegmentId', 'timestamp', 'text'],
                properties: {
                  startSegmentId: { type: 'string' },
                  endSegmentId: { type: 'string' },
                  timestamp: { type: 'string' },
                  text: { type: 'string', minLength: 3, maxLength: 300 },
                },
              },
            },
          },
        },
      },
    },
  },
};

export function buildCandidateClippingPrompt(input: {
  chunkTitle: string;
  chunkSummary: string;
  chunkSegments: string;
  targetLanguage: string;
}): ProviderPrompt {
  return {
    system: `
You extract reusable candidate clippings from a topic chunk.

Keep candidates neutral. Do not classify them as startup ideas, investment ideas, research notes, learning notes, or content ideas.

Rules:
- Extract only useful, high-signal ideas grounded in the chunk.
- Each candidate must include at least one sourceRef using segment IDs from the chunk.
- Use only transcript content. Do not invent facts.
- Write title, text, brief, level1, level2, and level3 in ${input.targetLanguage}.

Return only JSON matching the schema.
`.trim(),
    user: `Chunk title: ${input.chunkTitle}
Chunk summary: ${input.chunkSummary}
Chunk segments:
${input.chunkSegments}`,
  };
}
