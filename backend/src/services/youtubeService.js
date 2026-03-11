const path = require("path");
const { spawn } = require("child_process");
const { AppError } = require("../middleware/errorHandler");

function extractVideoId(youtubeUrl) {
  let parsed;
  try {
    parsed = new URL(youtubeUrl);
  } catch {
    throw new AppError(400, "INVALID_YOUTUBE_URL", "youtubeUrl must be a valid URL");
  }

  const host = parsed.hostname.replace(/^www\./, "").toLowerCase();

  if (host === "youtu.be") {
    const id = parsed.pathname.slice(1).trim();
    if (!id) {
      throw new AppError(400, "INVALID_YOUTUBE_URL", "Missing video id in URL");
    }
    return id;
  }

  if (host === "youtube.com" || host === "m.youtube.com") {
    const watchId = parsed.searchParams.get("v");
    if (watchId) {
      return watchId;
    }

    if (parsed.pathname.startsWith("/shorts/")) {
      const shortId = parsed.pathname.split("/")[2];
      if (shortId) {
        return shortId;
      }
    }
  }

  throw new AppError(400, "INVALID_YOUTUBE_URL", "Unsupported YouTube URL format");
}

function fetchTranscriptViaPython(videoId) {
  const pythonBin = process.env.PYTHON_BIN || "python3";
  const scriptPath = path.resolve(__dirname, "../../scripts/fetch_transcript.py");

  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [scriptPath, videoId]);

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", () => {
      reject(new AppError(502, "PYTHON_RUNTIME_ERROR", "Unable to execute Python runtime"));
    });

    child.on("close", (code) => {
      if (code !== 0) {
        const trimmed = stderr.trim();

        if (trimmed.includes("PY_DEP_MISSING")) {
          reject(
            new AppError(
              500,
              "PYTHON_DEPENDENCY_MISSING",
              "Python package youtube-transcript-api is not installed"
            )
          );
          return;
        }

        if (trimmed.includes("TRANSCRIPT_UNAVAILABLE")) {
          reject(new AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video"));
          return;
        }

        reject(new AppError(502, "TRANSCRIPT_FETCH_FAILED", "Unable to fetch YouTube transcript"));
        return;
      }

      let parsed;
      try {
        parsed = JSON.parse(stdout);
      } catch {
        reject(new AppError(502, "TRANSCRIPT_PARSE_FAILED", "Invalid transcript response"));
        return;
      }

      const transcriptText = typeof parsed?.transcriptText === "string" ? parsed.transcriptText : "";
      const transcriptSnippets = Array.isArray(parsed?.transcriptSnippets) ? parsed.transcriptSnippets : [];
      const languageCode = typeof parsed?.languageCode === "string" ? parsed.languageCode : null;
      const language = typeof parsed?.language === "string" ? parsed.language : null;
      const isGenerated = typeof parsed?.isGenerated === "boolean" ? parsed.isGenerated : null;

      resolve({
        transcriptText,
        transcriptSnippets,
        languageCode,
        language,
        isGenerated,
      });
    });
  });
}

async function fetchTranscriptText(youtubeUrl) {
  const videoId = extractVideoId(youtubeUrl);
  const { transcriptText, transcriptSnippets, languageCode, language, isGenerated } =
    await fetchTranscriptViaPython(videoId);

  if (!transcriptText.trim()) {
    throw new AppError(502, "TRANSCRIPT_UNAVAILABLE", "Transcript unavailable for this video");
  }

  return {
    videoId,
    transcriptText,
    transcriptSnippets,
    languageCode,
    language,
    isGenerated,
  };
}

module.exports = {
  fetchTranscriptText,
};
