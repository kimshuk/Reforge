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
                  brief: { type: 'string', maxLength: 60 },
                  level1: { type: 'string', maxLength: 120 },
                  level2: { type: 'string', maxLength: 240 },
                  level3: { type: 'string', maxLength: 320 },
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
- brief: 5-12 words.
- level1: up to 15 words.
- level2: up to 30 words.
- level3: up to 40 words.
- Use only transcript content. Do not infer or fabricate.

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
