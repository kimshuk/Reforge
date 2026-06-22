import { ProviderPrompt, TranscriptType } from './llm.types';

export const CATEGORY_EXTRACTION_SCHEMA = {
  name: 'category_extraction',
  strict: true,
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['sourceType', 'categories'],
    properties: {
      sourceType: {
        type: 'string',
        enum: ['youtube', 'manual'],
      },
      categories: {
        type: 'array',
        minItems: 1,
        maxItems: 6,
        items: {
          type: 'object',
          additionalProperties: false,
          required: ['title', 'keywords'],
          properties: {
            title: {
              type: 'string',
              minLength: 3,
              maxLength: 80,
            },
            keywords: {
              type: 'array',
              minItems: 3,
              maxItems: 8,
              items: {
                type: 'object',
                additionalProperties: false,
                required: ['term', 'brief', 'level1', 'level2', 'level3', 'source'],
                properties: {
                  term: { type: 'string', minLength: 2, maxLength: 60 },
                  brief: { type: 'string', minLength: 3, maxLength: 90 },
                  level1: { type: 'string', minLength: 3, maxLength: 180 },
                  level2: { type: 'string', minLength: 3, maxLength: 420 },
                  level3: { type: 'string', minLength: 3, maxLength: 700 },
                  source: {
                    type: 'object',
                    additionalProperties: false,
                    required: ['type', 'ref'],
                    properties: {
                      type: { type: 'string', enum: ['youtube', 'manual'] },
                      ref: { type: 'string', maxLength: 240 },
                    },
                  },
                },
              },
            },
          },
        },
      },
    },
  },
};

export function buildCategoryExtractionPrompt(input: {
  transcriptText: string;
  transcriptType: TranscriptType;
  targetLanguage: string;
  youtubeUrl?: string;
}): ProviderPrompt {
  return {
    system: `
You are a transcript topic-structure extraction engine.

Organize transcript content into topic-based categories and related keywords.

CATEGORIES
- A category is a major topic discussed in the transcript.
- Return 1 category for tightly focused transcripts.
- Return 2-4 categories when multiple topics appear.
- Return up to 6 categories only when clearly supported.
- Category titles must be 2-6 words.
- Categories must differ by subject matter, not abstraction level.

KEYWORDS
- Return 3-5 keywords per category.
- Keywords must be 2-6 words and transcript-specific.
- Do not duplicate or rephrase keywords.

DESCRIPTIONS
- The keyword fields are a progressive explanation ladder, not repeated paraphrases.
- term: short reusable concept label, preferably a noun phrase, not a sentence.
- brief: 5-10 word glanceable explanation; shorter than level1.
- level1: one simple beginner-friendly definition of the term. It should explain what the term means without relying on the video context.
- level2: 2-3 sentence contextual explanation of how the term appears in this specific video/topic chunk. It must stay grounded in the transcript.
- level3: 3-5 sentence detailed explanation that includes the speaker's claim, reasoning, mechanism, implication, risk, or example when available. It must be source-grounded and should not introduce external facts.
- level1, level2, and level3 must not be empty, duplicates, or repeated paraphrases. Each level must add new detail.
- Use only transcript content. Do not infer or fabricate.

Good keyword example:
{
  "term": "Pricing Pressure",
  "brief": "Competitors are pushing prices down",
  "level1": "Pricing pressure means outside forces make prices harder to maintain.",
  "level2": "In this transcript, the speaker says competitors are pushing prices down. They connect that pressure to the team needing a clearer response.",
  "level3": "The speaker claims competitors are pushing prices down and making the current approach harder to defend. Their reasoning is that buyers now compare options more directly, so the team needs a clearer response. The implication is that pricing cannot be treated as a static decision in this part of the discussion."
}

Bad keyword example:
{
  "term": "Pricing is hard.",
  "brief": "Pricing is hard",
  "level1": "Pricing is hard.",
  "level2": "Pricing is hard.",
  "level3": "Pricing is hard."
}

OUTPUT LANGUAGE
- Write category titles, keyword terms, brief, level1, level2, and level3 in ${input.targetLanguage}.
- Keep source.type and source.ref machine-readable.

SOURCE RULES
Every keyword must include a non-empty source object.

For transcriptType = "youtube":
- Transcript lines are formatted as "S### | MM:SS | text".
- Set source.type = "youtube".
- Set source.ref to an existing MM:SS timestamp from the transcript.
- Never invent timestamps or return segment ids, URLs, excerpts, arrays, null, or empty strings.

For transcriptType = "manual":
- Set source.type = "manual".
- Set source.ref to a verbatim excerpt of 25 words or fewer that directly references the keyword.

Return only valid JSON matching this shape:
{
  "sourceType": "youtube" | "manual",
  "categories": [
    {
      "title": "string",
      "keywords": [
        {
          "term": "string",
          "brief": "string",
          "level1": "string",
          "level2": "string",
          "level3": "string",
          "source": { "type": "youtube" | "manual", "ref": "string" }
        }
      ]
    }
  ]
}
`.trim(),
    user: `Transcript type: ${input.transcriptType}
Target language: ${input.targetLanguage}
YouTube base URL: ${input.youtubeUrl || 'N/A'}
Transcript:
${input.transcriptText}`,
  };
}
