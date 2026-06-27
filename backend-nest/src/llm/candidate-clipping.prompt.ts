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
            'simpleExplanation',
            'contextualExplanation',
            'detailedExplanation',
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
            title: { type: 'string', minLength: 2, maxLength: 60 },
            text: { type: 'string', minLength: 3, maxLength: 500 },
            brief: { type: 'string', minLength: 3, maxLength: 90 },
            simpleExplanation: { type: 'string', minLength: 3, maxLength: 180 },
            contextualExplanation: { type: 'string', minLength: 3, maxLength: 420 },
            detailedExplanation: { type: 'string', minLength: 3, maxLength: 700 },
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
- Write title, text, brief, simpleExplanation, contextualExplanation, and detailedExplanation in ${input.targetLanguage}.

Explanation ladder contract:
- title is the compatibility term: a short reusable concept label, preferably a noun phrase, not a sentence.
- brief is a 5-10 word glanceable explanation and must be shorter than simpleExplanation.
- simpleExplanation is one simple beginner-friendly definition of the title. It explains what the term means without relying on this video context.
- contextualExplanation is 2-3 sentences explaining how the term appears in this specific chunk. It must stay grounded in the transcript.
- detailedExplanation is 3-5 sentences with the speaker's claim, reasoning, mechanism, implication, risk, or example when available. It must be source-grounded and must not introduce external facts.
- simpleExplanation, contextualExplanation, and detailedExplanation must not be empty, duplicated, or repeated paraphrases. Each level must add new detail.

Good example:
{
  "title": "Pricing Pressure",
  "brief": "Competitors are pushing prices down",
  "simpleExplanation": "Pricing pressure means outside forces make prices harder to maintain.",
  "contextualExplanation": "In this chunk, the speaker says competitors are pushing prices down. They connect that pressure to the team needing a clearer response.",
  "detailedExplanation": "The speaker claims competitors are pushing prices down and making the current approach harder to defend. Their reasoning is that buyers now compare options more directly, so the team needs a clearer response. The implication is that pricing cannot be treated as a static decision in this part of the discussion."
}

Bad example:
{
  "title": "Pricing is hard.",
  "brief": "Pricing is hard",
  "simpleExplanation": "Pricing is hard.",
  "contextualExplanation": "Pricing is hard.",
  "detailedExplanation": "Pricing is hard."
}

Return only JSON matching the schema.
`.trim(),
    user: `Chunk title: ${input.chunkTitle}
Chunk summary: ${input.chunkSummary}
Chunk segments:
${input.chunkSegments}`,
  };
}
