const express = require("express");
const { validateAnalyzeBody, assertTranscriptText } = require("../services/transcriptValidator");
const { fetchTranscriptText } = require("../services/youtubeService");
const transcriptStore = require("../services/transcriptStore");
const { analyzeCategories } = require("../services/openaiService");
const { sanitizeYoutubeTranscript } = require("../services/transcriptSanitizer");
const logger = require("../services/logger");

const router = express.Router();

router.post("/", async (req, res, next) => {
  try {
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

    let videoId = null;
    let transcriptText = "";
    let segmentIndex = [];
    let cleanedSnippetCount = null;

    if (source.type === "youtube") {
      const youtubeResult = await fetchTranscriptText(source.youtubeUrl);
      videoId = youtubeResult.videoId;
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
    } else {
      transcriptText = source.text;
    }

    const normalizedTranscript = assertTranscriptText(transcriptText);

    const transcriptId = transcriptStore.setTranscript({
      transcriptText: normalizedTranscript,
      videoId,
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

    res.status(200).json(response);
  } catch (error) {
    next(error);
  }
});

module.exports = router;
