const { randomUUID } = require("crypto");

const TTL_MS = 60 * 60 * 1000;
const store = new Map();

function setTranscript({ transcriptText, videoId }) {
  const transcriptId = randomUUID();
  const now = Date.now();

  store.set(transcriptId, {
    transcriptText,
    videoId,
    createdAt: now,
    expiresAt: now + TTL_MS,
  });

  return transcriptId;
}

function getTranscript(transcriptId) {
  const entry = store.get(transcriptId);
  if (!entry) {
    return null;
  }

  if (entry.expiresAt <= Date.now()) {
    store.delete(transcriptId);
    return null;
  }

  return entry;
}

function cleanupExpired() {
  const now = Date.now();
  for (const [key, entry] of store.entries()) {
    if (entry.expiresAt <= now) {
      store.delete(key);
    }
  }
}

const interval = setInterval(cleanupExpired, 60 * 1000);
interval.unref();

module.exports = {
  TTL_MS,
  setTranscript,
  getTranscript,
  cleanupExpired,
};
