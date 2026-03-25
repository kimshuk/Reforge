const CATEGORY_EXTRACTION_SCHEMA = {
  name: 'category_extraction',
  schema: {
    type: 'object',
    additionalProperties: false,
    required: ['sourceType', 'categories'],
    properties: {
      sourceType: {
        type: 'string',
        enum: ['youtube', 'manual']
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
              pattern: "^(\\S+\\s+){1,5}\\S+$"
            },
            keywords: {
              type: 'array',
              minItems: 3,
              maxItems: 8,
              items: {
                type: 'object',
                additionalProperties: false,
                required: [
                  'term',
                  'brief',
                  'level1',
                  'level2',
                  'level3',
                  'source'
                ],
                properties: {
                  term: {
                    type: 'string',
                    minLength: 2,
                    maxLength: 60,
                    pattern: "^(\\S+\\s+){1,5}\\S+$"
                  },
                  brief: {
                    type: 'string',
                    maxLength: 60
                  },
                  level1: {
                    type: 'string',
                    maxLength: 120
                  },
                  level2: {
                    type: 'string',
                    maxLength: 240
                  },
                  level3: {
                    type: 'string',
                    maxLength: 320
                  },
                  source: {
                    type: 'object',
                    additionalProperties: false,
                    required: ['type', 'ref'],
                    properties: {
                      type: {
                        type: 'string',
                        enum: ['youtube', 'manual']
                      },
                      ref: {
                        type: 'string',
                        maxLength: 240
                      }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  strict: true
};

function buildCategoryExtractionPrompt({
  transcriptText,
  transcriptType, // 'youtube' | 'manual'
  youtubeUrl = '',
  targetLanguage = 'en'
}) {
  return [
    {
      role: 'system',
      content: `
You are a transcript topic–structure extraction engine.

Your task is to organize transcript content into topic-based categories and related keywords.

CATEGORIES

A category represents a major topic discussed in the transcript.

Categories group keywords that belong to the same topic area.

A transcript may contain:
- 1 category if the discussion is tightly focused.
- 2–4 categories when multiple topics appear.
- Up to 6 categories only when clearly supported.

CATEGORY RULES

- Title: 2–6 words.
- Must describe a clear topic discussed in the transcript.
- Categories must differ in subject matter, not abstraction level.
- Do not collapse multiple topics into one umbrella category.
- Each category should represent a coherent section of discussion.

Examples of valid separation:

AI Model Scaling  
AI Startup Funding  
AI Distribution Strategy  
AI Safety Concerns

SECTION DETECTION

Before extracting categories:

1. Detect major discussion sections in the transcript.
2. Each section likely corresponds to one category.
3. Use those sections to guide category formation.

COVERAGE RULE

Keywords within a category must refer to the same topic.

If a keyword clearly belongs to another topic,
create a new category instead of forcing it into the current category.

Do not mix unrelated keywords in the same category.

KEYWORDS

- 3–5 keywords per category.
- 2–6 words each.
- Transcript-specific phrases.
- No duplication or rephrasing.

If more than 5 keywords are needed,
create another category instead.

DESCRIPTIONS (per keyword)

Include:

brief
- 5–12 words.
- Hint only.

level1
- ≤15 words.
- Direct factual statement.

level2
- ≤30 words.
- Add explicit transcript details.
- Expand without repeating.

level3
- ≤40 words.
- Most detailed reconstruction using only transcript content.
- May combine explicit statements.
- No inference or added reasoning.

If insufficient detail exists, do not fabricate.

OUTPUT LANGUAGE

- Write all model-generated text in the requested target language: ${targetLanguage}.
- This applies to category titles, keyword terms, brief, level1, level2, and level3.
- Keep source.type and source.ref in their required machine-readable formats.
- Do not translate or rewrite the transcript itself.

STYLE (generated text)

- Easy reading level.
- Clear, direct wording.
- Prefer short sentences.
- Use multiple simple sentences instead of complex ones.
- No jargon, abstract language, metaphors, rhetorical tone, or academic phrasing.

SOURCE

Each keyword must include "source".
Every keyword must include a non-empty source object.
Do not omit source for any keyword.

If transcriptType = "youtube":

Transcript lines are formatted as:

"S### | MM:SS | text"

Rules:

- Set source.type = "youtube".
- Set source.ref to exactly one segment ID (example: "S014").
- Use only IDs that exist in the transcript.
- Never invent segment IDs.
- Never return a URL, timestamp, sentence, excerpt, array, null, or empty string in source.ref.
- Never omit source or source.ref, even if evidence is weak.
- If you cannot find a valid segment ID for a candidate keyword, do not output that keyword.
- Choose the segment where the keyword is explicitly discussed.

If transcriptType = "manual":

- Provide verbatim excerpt ≤25 words.
- Must directly reference the keyword.
- No paraphrasing.

Set:

source.type = "manual"  
source.ref = excerpt text

STRICT RULES

- No interpretation.
- No evaluation.
- No speculation.
- No commentary outside JSON.
- Do not mix unrelated topics into one category.
- Categories must remain semantically coherent.

Return only valid structured JSON.
`
    },
    {
      role: 'user',
      content: `Transcript type: ${transcriptType}\nTarget language: ${targetLanguage}\nYouTube base URL: ${youtubeUrl || 'N/A'}\nTranscript:\n${transcriptText}`
    }
  ];
}

module.exports = {
  CATEGORY_EXTRACTION_SCHEMA,
  buildCategoryExtractionPrompt,
};
