const DEFAULTS = {
  minSegmentSeconds: 20,
  maxSegmentSeconds: 35,
  hardMaxSegmentSeconds: 45,
  minSegmentChars: 180,
  maxSegmentChars: 320,
  hardMaxSegmentChars: 420,
  pauseSplitSeconds: 2.5,
};

const BRACKET_NOISE_PATTERN =
  /^(music|applause|laugh(?:ter)?|noise|silence|bgm|audience|clap|박수|웃음|음악)$/i;

function formatTimestamp(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;

  if (h > 0) {
    return `${String(h)}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function flattenRawSnippets(input, out = []) {
  if (Array.isArray(input)) {
    for (const item of input) {
      flattenRawSnippets(item, out);
    }
    return out;
  }

  if (input && typeof input === "object") {
    out.push(input);
  }

  return out;
}

function stripBracketNoise(text) {
  return text
    .replace(/\[([^\]]{1,30})\]/g, (match, content) => (BRACKET_NOISE_PATTERN.test(content.trim()) ? " " : match))
    .replace(/\(([^)]{1,30})\)/g, (match, content) => (BRACKET_NOISE_PATTERN.test(content.trim()) ? " " : match));
}

function normalizeText(input) {
  if (typeof input !== "string") {
    return "";
  }

  let text = input;
  text = text.replace(/^\s*>+\s*/g, " ");
  text = stripBracketNoise(text);
  text = text.replace(/(ㅋ){3,}/g, "ㅋㅋ");
  text = text.replace(/(ㅎ){3,}/g, "ㅎㅎ");
  text = text.replace(/([!?.,~])\1{2,}/g, "$1$1");
  text = text.replace(/\s+/g, " ").trim();

  if (/^[>|~\-_=.,!?]+$/.test(text)) {
    return "";
  }

  return text;
}

function sanitizeSnippetList(rawSnippets) {
  const flattened = flattenRawSnippets(rawSnippets);
  const snippets = [];

  for (const item of flattened) {
    const startSec = Number(item?.start);
    if (!Number.isFinite(startSec) || startSec < 0) {
      continue;
    }

    const durationSec = Number(item?.duration);
    const safeDuration = Number.isFinite(durationSec) && durationSec > 0 ? durationSec : 0;
    const text = normalizeText(item?.text);

    if (!text) {
      continue;
    }

    snippets.push({
      startSec,
      endSec: startSec + safeDuration,
      durationSec: safeDuration,
      text,
    });
  }

  snippets.sort((a, b) => a.startSec - b.startSec);
  return snippets;
}

function shouldSplitSegment(segment, nextSnippet, cfg) {
  if (!segment) {
    return false;
  }

  const pause = nextSnippet.startSec - segment.endSec;
  if (pause > cfg.pauseSplitSeconds) {
    return true;
  }

  const nextEnd = Math.max(segment.endSec, nextSnippet.endSec);
  const nextDuration = nextEnd - segment.startSec;
  const nextChars = segment.charCount + 1 + nextSnippet.text.length;

  if (nextDuration > cfg.maxSegmentSeconds || nextChars > cfg.maxSegmentChars) {
    const readyToSplit =
      segment.duration >= cfg.minSegmentSeconds || segment.charCount >= cfg.minSegmentChars;
    if (readyToSplit) {
      return true;
    }

    if (nextDuration > cfg.hardMaxSegmentSeconds || nextChars > cfg.hardMaxSegmentChars) {
      return true;
    }
  }

  return false;
}

function buildSegments(snippets, options = {}) {
  const cfg = { ...DEFAULTS, ...options };
  const segments = [];
  let current = null;

  const finalizeCurrent = () => {
    if (!current || !current.parts.length) {
      current = null;
      return;
    }

    const text = current.parts.join(" ").replace(/\s+/g, " ").trim();
    if (!text) {
      current = null;
      return;
    }

    segments.push({
      startSec: current.startSec,
      endSec: current.endSec,
      text,
    });
    current = null;
  };

  for (const snippet of snippets) {
    if (!current) {
      current = {
        startSec: snippet.startSec,
        endSec: snippet.endSec,
        parts: [snippet.text],
        charCount: snippet.text.length,
        duration: Math.max(0, snippet.endSec - snippet.startSec),
      };
      continue;
    }

    if (shouldSplitSegment(current, snippet, cfg)) {
      finalizeCurrent();
      current = {
        startSec: snippet.startSec,
        endSec: snippet.endSec,
        parts: [snippet.text],
        charCount: snippet.text.length,
        duration: Math.max(0, snippet.endSec - snippet.startSec),
      };
      continue;
    }

    current.parts.push(snippet.text);
    current.endSec = Math.max(current.endSec, snippet.endSec);
    current.charCount += 1 + snippet.text.length;
    current.duration = Math.max(0, current.endSec - current.startSec);
  }

  finalizeCurrent();

  const segmentIndex = segments.map((segment, index) => ({
    id: `S${String(index + 1).padStart(3, "0")}`,
    startSec: segment.startSec,
    endSec: segment.endSec,
    text: segment.text,
  }));

  const llmTranscriptText = segmentIndex
    .map((segment) => `${segment.id} | ${formatTimestamp(segment.startSec)} | ${segment.text}`)
    .join("\n");

  return {
    llmTranscriptText,
    segmentIndex,
  };
}

function sanitizeYoutubeTranscript(rawSnippets, options = {}) {
  const cleanedSnippets = sanitizeSnippetList(rawSnippets);
  const { llmTranscriptText, segmentIndex } = buildSegments(cleanedSnippets, options);

  return {
    llmTranscriptText,
    segmentIndex,
    cleanedSnippetCount: cleanedSnippets.length,
  };
}

module.exports = {
  sanitizeYoutubeTranscript,
};
