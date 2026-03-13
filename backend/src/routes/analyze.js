const express = require("express");
const { validateAnalyzeBody, assertTranscriptText } = require("../services/transcriptValidator");
const { fetchTranscriptText } = require("../services/youtubeService");
const transcriptStore = require("../services/transcriptStore");
const { analyzeCategories } = require("../services/openaiService");
const { sanitizeYoutubeTranscript } = require("../services/transcriptSanitizer");
const logger = require("../services/logger");

const router = express.Router();

function wantsProgressStream(req) {
  const accept = String(req.get("accept") || "").toLowerCase();
  const streamQuery = String(req.query.stream || "").toLowerCase();
  return accept.includes("text/event-stream") || streamQuery === "progress";
}

function writeSseEvent(res, event, data) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(data)}\n\n`);
}

function startSse(res) {
  res.status(200);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders?.();
}

async function performAnalyze(req, emitProgress = null) {
  const source = validateAnalyzeBody(req.body);

  logger.info("analyze.request", {
    requestId: req.requestId,
    path: req.path,
    type: source.type,
    targetLanguage: source.targetLanguage,
    hasYoutubeUrl: source.type === "youtube",
    hasText: source.type === "manual",
    hasTitle: Boolean(source.title),
  });

  emitProgress?.("started", {
    stage: "started",
    message: "Accepted analyze request",
    type: source.type,
  });

  let videoId = null;
  let transcriptText = "";
  let segmentIndex = [];
  let cleanedSnippetCount = null;

  if (source.type === "youtube") {
    emitProgress?.("progress", {
      stage: "fetching_transcript",
      message: "Fetching YouTube transcript",
    });

    const youtubeResult = await fetchTranscriptText(source.youtubeUrl);
    videoId = youtubeResult.videoId;

    emitProgress?.("progress", {
      stage: "sanitizing_transcript",
      message: "Preparing transcript for analysis",
      videoId,
    });

    const sanitized = sanitizeYoutubeTranscript(youtubeResult.transcriptSnippets);
    transcriptText = sanitized.llmTranscriptText;
    segmentIndex = sanitized.segmentIndex;
    cleanedSnippetCount = sanitized.cleanedSnippetCount;

    logger.info("analyze.transcript_language", {
      requestId: req.requestId,
      videoId: youtubeResult.videoId,
      languageCode: youtubeResult.languageCode,
      language: youtubeResult.language,
      isGenerated: youtubeResult.isGenerated,
      snippetCount: Array.isArray(youtubeResult.transcriptSnippets)
        ? youtubeResult.transcriptSnippets.length
        : 0,
      cleanedSnippetCount,
      segmentCount: segmentIndex.length,
    });

    emitProgress?.("progress", {
      stage: "transcript_ready",
      message: "Transcript prepared",
      videoId,
      segmentCount: segmentIndex.length,
    });
  } else {
    transcriptText = source.text;
  }

  const normalizedTranscript = assertTranscriptText(transcriptText);

  emitProgress?.("progress", {
    stage: "storing_transcript",
    message: "Caching transcript",
  });

  const transcriptId = transcriptStore.setTranscript({
    transcriptText: normalizedTranscript,
    videoId,
  });

  emitProgress?.("progress", {
    stage: "analyzing_categories",
    message: "Sending transcript to OpenAI for categorization",
    transcriptId,
  });

  const analysis = await analyzeCategories({
    transcriptText: normalizedTranscript,
    transcriptType: source.type,
    targetLanguage: source.targetLanguage,
    youtubeUrl: source.type === "youtube" ? source.youtubeUrl : "",
    segmentIndex: source.type === "youtube" ? segmentIndex : [],
  });

  const response = {
    transcriptId,
    sourceType: analysis.sourceType,
    categories: analysis.categories,
    expiresInSeconds: transcriptStore.TTL_MS / 1000,
  };

  if (videoId) {
    response.videoId = videoId;
  }

  emitProgress?.("completed", {
    stage: "completed",
    message: "Analysis complete",
    transcriptId,
    categoryCount: response.categories.length,
  });

  return response;
}

router.post("/", async (req, res, next) => {
  if (!wantsProgressStream(req)) {
    try {
      const response = await performAnalyze(req);
      res.status(200).json(response);
    } catch (error) {
      next(error);
    }
    return;
  }

  startSse(res);

  try {
    const response = await performAnalyze(req, (event, payload) => {
      writeSseEvent(res, event, payload);
    });

    writeSseEvent(res, "result", response);
    res.end();
  } catch (error) {
    const statusCode = Number.isInteger(error?.statusCode) ? error.statusCode : 500;
    const code = typeof error?.code === "string" ? error.code : "INTERNAL_SERVER_ERROR";
    const message = typeof error?.message === "string" ? error.message : "Unexpected server error";

    writeSseEvent(res, "error", {
      stage: "failed",
      statusCode,
      code,
      message,
    });
    res.end();
  }
});

module.exports = router;
