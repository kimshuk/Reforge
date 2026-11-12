const ANALYSIS_FAILED = "We couldn't finish analyzing this video. Please try again."

const MESSAGES: Record<string, string> = {
  INVALID_YOUTUBE_URL: "That doesn't look like a YouTube video link.",
  TRANSCRIPT_UNAVAILABLE: "This video doesn't have a transcript we can use.",
  TRANSCRIPT_FETCH_FAILED: "We couldn't fetch the transcript. Please try again.",
  EMPTY_TRANSCRIPT: 'This video has an empty transcript.',
  SHORT_TRANSCRIPT: 'This video is too short to analyze.',
  LLM_QUOTA_OR_RATE_LIMIT: 'The analysis service is busy. Please try again shortly.',
  LLM_CONTEXT_LENGTH_EXCEEDED: 'This video is too long to analyze.',
  LLM_AUTH_ERROR: "The analysis service isn't available right now.",
  LLM_PROVIDER_NOT_CONFIGURED: "The analysis service isn't available right now.",
  LLM_CLIPPINGS_INVALID_JSON: ANALYSIS_FAILED,
  LLM_CLIPPINGS_INVALID_SOURCE_REF: ANALYSIS_FAILED,
  LLM_TOPIC_CHUNKS_EMPTY: ANALYSIS_FAILED,
  LLM_TOPIC_CHUNKS_INVALID_BOUNDARY: ANALYSIS_FAILED,
  LLM_TOPIC_CHUNKS_INVALID_JSON: ANALYSIS_FAILED,
  LLM_CATEGORY_GROUPING_INVALID_JSON: ANALYSIS_FAILED,
  LLM_EMPTY_OUTPUT: ANALYSIS_FAILED,
  LLM_RESPONSE_INCOMPLETE: ANALYSIS_FAILED,
  LLM_REQUEST_FAILED: ANALYSIS_FAILED,
  INVALID_CATEGORY_GRAPH: ANALYSIS_FAILED,
  INTERNAL_SERVER_ERROR: ANALYSIS_FAILED,
  NETWORK_ERROR: "Couldn't reach the server.",
  MISSING_RESULT: 'The server finished without returning data.',
  INVALID_RESPONSE: 'The server sent a response we could not read.',
}

export function messageForError(code: string, serverMessage: string): string {
  return MESSAGES[code] ?? (serverMessage.trim() || 'Something went wrong. Please try again.')
}
