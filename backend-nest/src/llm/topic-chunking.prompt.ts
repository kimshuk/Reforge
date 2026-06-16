import { ProviderPrompt } from './llm.types';

export const TOPIC_CHUNKING_SCHEMA = {
  name: 'topic_chunking',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['topicChunks'],
    properties: {
      topicChunks: {
        type: 'array',
        minItems: 1,
        items: {
          type: 'object',
          additionalProperties: false,
          required: [
            'startSegmentId',
            'endSegmentId',
            'title',
            'summary',
            'signalLevel',
          ],
          properties: {
            startSegmentId: { type: 'string' },
            endSegmentId: { type: 'string' },
            title: { type: 'string', minLength: 3, maxLength: 80 },
            summary: { type: 'string', minLength: 3, maxLength: 300 },
            signalLevel: {
              type: 'string',
              enum: ['high', 'medium', 'low', 'off_topic'],
            },
          },
        },
      },
    },
  },
};

export function buildTopicChunkingPrompt(input: {
  transcriptSegments: string;
  targetLanguage: string;
}): ProviderPrompt {
  return {
    system: `
You split transcript segments into coherent topic chunks.

Return boundaries only. Do not write chunk text.

Rules:
- Use only segment IDs that appear in the transcript.
- Chunks must be ordered and non-overlapping.
- Each major topic shift should become a chunk.
- Sponsor reads, intros, repeated content, and tangents should be low or off_topic when large enough to affect coverage.
- Write title and summary in ${input.targetLanguage}.

Return only JSON matching the schema.
`.trim(),
    user: `Transcript segments:
${input.transcriptSegments}`,
  };
}
