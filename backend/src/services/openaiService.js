const openai = require("../config/openai");
const { AppError } = require("../middleware/errorHandler");
const {
  CATEGORY_EXTRACTION_SCHEMA,
  buildCategoryExtractionPrompt,
} = require("./promptBuilder");

const MODEL = "gpt-4o-mini";
const TEMPERATURE = 0.2;

function toOpenAiAppError(error, fallbackCode, fallbackMessage) {
  const status = Number.isInteger(error?.status) ? error.status : 502;
  const apiCode = typeof error?.code === "string" ? error.code : null;
  const apiMessage = typeof error?.message === "string" ? error.message : fallbackMessage;

  if (status === 401 || apiCode === "invalid_api_key") {
    return new AppError(502, "OPENAI_AUTH_ERROR", apiMessage);
  }

  if (status === 429 || apiCode === "insufficient_quota" || apiCode === "rate_limit_exceeded") {
    return new AppError(502, "OPENAI_QUOTA_OR_RATE_LIMIT", apiMessage);
  }

  if (apiCode === "context_length_exceeded") {
    return new AppError(502, "OPENAI_CONTEXT_LENGTH_EXCEEDED", apiMessage);
  }

  if (status === 400) {
    return new AppError(502, "OPENAI_BAD_REQUEST", apiMessage);
  }

  return new AppError(502, fallbackCode, apiMessage);
}

function parseStructuredOutput(rawText, errorCode) {
  const normalized = String(rawText || "")
    .trim()
    .replace(/^```json\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```$/, "")
    .trim();

  if (!normalized) {
    throw new AppError(502, `${errorCode}_EMPTY`, "Model returned empty output");
  }

  try {
    return JSON.parse(normalized);
  } catch {
    throw new AppError(502, errorCode, "Model returned invalid JSON");
  }
}

function toYoutubeTimestampUrl(youtubeUrl, startSec) {
  const url = new URL(youtubeUrl);
  url.searchParams.set("t", `${Math.max(0, Math.floor(Number(startSec) || 0))}s`);
  return url.toString();
}

function resolveYoutubeSources(payload, youtubeUrl, segmentIndex) {
  if (!Array.isArray(segmentIndex) || segmentIndex.length === 0) {
    throw new AppError(502, "OPENAI_INVALID_SOURCE_REF", "No transcript segments available for citation");
  }

  const indexById = new Map();
  for (const segment of Array.isArray(segmentIndex) ? segmentIndex : []) {
    if (segment && typeof segment.id === "string") {
      indexById.set(segment.id.trim().toUpperCase(), segment);
    }
  }

  for (const category of payload.categories) {
    if (!category || !Array.isArray(category.keywords)) {
      continue;
    }

    for (const keyword of category.keywords) {
      const source = keyword?.source;
      if (!source) {
        throw new AppError(
          502,
          "OPENAI_INVALID_SOURCE_REF",
          "YouTube keyword source must be a segment ID reference"
        );
      }

      const rawRef = typeof source.ref === "string" ? source.ref.trim().toUpperCase() : "";
      if (!rawRef) {
        throw new AppError(502, "OPENAI_INVALID_SOURCE_REF", "Missing source segment reference");
      }

      const segment = indexById.get(rawRef);
      if (!segment) {
        throw new AppError(
          502,
          "OPENAI_INVALID_SOURCE_REF",
          `Model returned unknown source segment ID: ${rawRef}`
        );
      }

      keyword.source.ref = toYoutubeTimestampUrl(youtubeUrl, segment.startSec);
    }
  }
}

async function analyzeCategories({
  transcriptText,
  transcriptType,
  targetLanguage = "en",
  youtubeUrl = "",
  segmentIndex = [],
}) {
  let response;
  try {
    response = await openai.responses.create({
      model: MODEL,
      temperature: TEMPERATURE,
      input: buildCategoryExtractionPrompt({
        transcriptText,
        transcriptType,
        targetLanguage,
        youtubeUrl,
      }),
      text: {
        format: {
          type: "json_schema",
          name: CATEGORY_EXTRACTION_SCHEMA.name,
          schema: CATEGORY_EXTRACTION_SCHEMA.schema,
          strict: CATEGORY_EXTRACTION_SCHEMA.strict,
        },
      },
    });
  } catch (error) {
    throw toOpenAiAppError(error, "OPENAI_ANALYZE_FAILED", "OpenAI analyze request failed");
  }

  if (response.status === "incomplete") {
    throw new AppError(502, "OPENAI_ANALYZE_INCOMPLETE", "OpenAI returned an incomplete response");
  }

  if (response.status === "failed") {
    throw new AppError(502, "OPENAI_ANALYZE_FAILED", "OpenAI response failed");
  }

  const payload = parseStructuredOutput(response.output_text || "", "OPENAI_ANALYZE_INVALID_JSON");

  if (payload.sourceType !== transcriptType) {
    throw new AppError(502, "OPENAI_ANALYZE_SOURCE_MISMATCH", "Model returned invalid sourceType");
  }

  if (!Array.isArray(payload.categories) || payload.categories.length === 0) {
    throw new AppError(502, "OPENAI_ANALYZE_EMPTY", "No categories returned");
  }

  if (transcriptType === "youtube") {
    resolveYoutubeSources(payload, youtubeUrl, segmentIndex);
  }

  return payload;
}
module.exports = {
  analyzeCategories,
};
