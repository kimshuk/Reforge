const { AppError } = require("../middleware/errorHandler");

const UUID_V4_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const TARGET_LANGUAGE_REGEX = /^[a-zA-Z]{2,3}(?:-[a-zA-Z]{4})?(?:-[a-zA-Z]{2}|\d{3})?$/;

function assertPlainObject(input, fieldName) {
  if (!input || typeof input !== "object" || Array.isArray(input)) {
    throw new AppError(400, "INVALID_REQUEST", `${fieldName} must be a JSON object`);
  }
}

function assertExactKeys(obj, allowedKeys) {
  const keys = Object.keys(obj);
  const sortedInput = [...keys].sort().join(",");
  const sortedAllowed = [...allowedKeys].sort().join(",");

  if (sortedInput !== sortedAllowed) {
    throw new AppError(
      400,
      "INVALID_REQUEST",
      `Request body must contain exactly: ${allowedKeys.join(", ")}`
    );
  }
}

function assertYoutubeUrl(value) {
  if (typeof value !== "string" || !value.trim()) {
    throw new AppError(400, "INVALID_YOUTUBE_URL", "youtubeUrl must be a non-empty string");
  }
}

function assertText(value) {
  if (typeof value !== "string" || !value.trim()) {
    throw new AppError(400, "INVALID_TEXT", "text must be a non-empty string");
  }
}

function assertOptionalTitle(value) {
  if (value === undefined) {
    return;
  }

  if (typeof value !== "string") {
    throw new AppError(400, "INVALID_TITLE", "title must be a string when provided");
  }

  if (!value.trim()) {
    throw new AppError(400, "INVALID_TITLE", "title must be non-empty when provided");
  }
}

function normalizeTargetLanguage(value) {
  if (value === undefined) {
    return "en";
  }

  if (typeof value !== "string" || !value.trim()) {
    throw new AppError(
      400,
      "INVALID_TARGET_LANGUAGE",
      "targetLanguage must be a non-empty BCP-47 language code"
    );
  }

  const trimmed = value.trim();
  if (!TARGET_LANGUAGE_REGEX.test(trimmed)) {
    throw new AppError(
      400,
      "INVALID_TARGET_LANGUAGE",
      "targetLanguage must be a valid BCP-47 language code"
    );
  }

  const parts = trimmed.split("-");
  return parts
    .map((part, index) => {
      if (index === 0) {
        return part.toLowerCase();
      }

      if (part.length === 4) {
        return `${part[0].toUpperCase()}${part.slice(1).toLowerCase()}`;
      }

      if (part.length === 2) {
        return part.toUpperCase();
      }

      return part;
    })
    .join("-");
}

function assertTranscriptId(value) {
  if (typeof value !== "string" || !UUID_V4_REGEX.test(value)) {
    throw new AppError(400, "INVALID_TRANSCRIPT_ID", "transcriptId must be a valid UUID v4");
  }
}

function assertTranscriptText(value) {
  if (typeof value !== "string") {
    throw new AppError(502, "INVALID_TRANSCRIPT", "Transcript text is invalid");
  }

  const trimmed = value.trim();
  if (!trimmed) {
    throw new AppError(502, "EMPTY_TRANSCRIPT", "Transcript is empty or unavailable");
  }

  if (trimmed.length < 80) {
    throw new AppError(502, "SHORT_TRANSCRIPT", "Transcript is too short for analysis");
  }

  return trimmed;
}

function validateAnalyzeBody(body) {
  assertPlainObject(body, "Request body");
  const { type } = body;

  if (type !== "youtube" && type !== "manual") {
    throw new AppError(400, "INVALID_TYPE", "type must be either 'youtube' or 'manual'");
  }

  assertOptionalTitle(body.title);
  const targetLanguage = normalizeTargetLanguage(body.targetLanguage);

  if (type === "youtube") {
    const allowed = ["type", "youtubeUrl"];
    if (body.title !== undefined) {
      allowed.push("title");
    }
    if (body.targetLanguage !== undefined) {
      allowed.push("targetLanguage");
    }
    assertExactKeys(body, allowed);
    assertYoutubeUrl(body.youtubeUrl);

    return {
      type: "youtube",
      title: body.title?.trim(),
      targetLanguage,
      youtubeUrl: body.youtubeUrl.trim(),
    };
  }

  const allowed = ["type", "text"];
  if (body.title !== undefined) {
    allowed.push("title");
  }
  if (body.targetLanguage !== undefined) {
    allowed.push("targetLanguage");
  }
  assertExactKeys(body, allowed);
  assertText(body.text);

  return {
    type: "manual",
    title: body.title?.trim(),
    targetLanguage,
    text: body.text.trim(),
  };
}

module.exports = {
  validateAnalyzeBody,
  assertTranscriptText,
  assertTranscriptId,
};
