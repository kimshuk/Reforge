const express = require("express");
const { AppError } = require("../middleware/errorHandler");
const transcriptStore = require("../services/transcriptStore");
const { assertTranscriptId } = require("../services/transcriptValidator");
const logger = require("../services/logger");

const router = express.Router();

router.get("/:transcriptId", (req, res, next) => {
  try {
    const transcriptId = req.params.transcriptId;
    assertTranscriptId(transcriptId);

    const cached = transcriptStore.getTranscript(transcriptId);
    if (!cached) {
      throw new AppError(404, "TRANSCRIPT_NOT_FOUND", "transcriptId not found or expired");
    }

    logger.info("transcript.fetch", {
      requestId: req.requestId,
      path: req.path,
      transcriptId,
      videoId: cached.videoId,
    });

    res.status(200).json({
      transcriptId,
      videoId: cached.videoId,
      createdAt: new Date(cached.createdAt).toISOString(),
      expiresAt: new Date(cached.expiresAt).toISOString(),
      transcriptText: cached.transcriptText,
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
