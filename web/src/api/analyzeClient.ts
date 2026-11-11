import { messageForError } from './errors'
import { createSseParser } from './sse'
import type { AnalyzeResponse } from './types'

const BASE_URL = (import.meta.env.VITE_BACKEND_BASE_URL ?? 'http://localhost:3000').replace(/\/$/, '')

export class AnalyzeError extends Error {
  readonly code: string

  constructor(code: string, serverMessage = '') {
    super(messageForError(code, serverMessage))
    this.code = code
  }
}

export interface AnalyzeHandlers {
  onStage: (stage: string) => void
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function parseJson<T>(raw: string): T {
  try {
    return JSON.parse(raw) as T
  } catch {
    throw new AnalyzeError('INVALID_RESPONSE')
  }
}

async function errorFromResponse(response: Response): Promise<AnalyzeError> {
  try {
    const body = (await response.json()) as { error?: { code?: string; message?: string } }
    if (body.error?.code) return new AnalyzeError(body.error.code, body.error.message)
  } catch {
    // Not an error envelope, for example a proxy error page.
  }
  return new AnalyzeError(`HTTP_${response.status}`)
}

async function readResult(
  body: ReadableStream<Uint8Array>,
  handlers: AnalyzeHandlers,
): Promise<AnalyzeResponse> {
  let result = null as AnalyzeResponse | null
  const parser = createSseParser(({ event, data }) => {
    if (event === 'result') {
      result = parseJson<AnalyzeResponse>(data)
    } else if (event === 'error') {
      const error = parseJson<{ code: string; message: string }>(data)
      throw new AnalyzeError(error.code, error.message)
    } else if (event === 'started' || event === 'progress' || event === 'completed') {
      handlers.onStage(parseJson<{ stage: string }>(data).stage)
    }
  })

  const decoder = new TextDecoder()
  const reader = body.getReader()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    parser.push(decoder.decode(value, { stream: true }))
  }
  if (!result) throw new AnalyzeError('MISSING_RESULT')
  return result
}

export async function analyzeVideo(
  youtubeUrl: string,
  handlers: AnalyzeHandlers,
  signal: AbortSignal,
): Promise<AnalyzeResponse> {
  try {
    const response = await fetch(`${BASE_URL}/analyze?stream=progress`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ type: 'youtube', youtubeUrl }),
      signal,
    })
    if (!response.ok) throw await errorFromResponse(response)
    if (!response.body) throw new AnalyzeError('MISSING_RESULT')
    return await readResult(response.body, handlers)
  } catch (error) {
    if (error instanceof AnalyzeError || isAbort(error)) throw error
    throw new AnalyzeError('NETWORK_ERROR')
  }
}
