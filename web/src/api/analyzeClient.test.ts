import { afterEach, describe, expect, it, vi } from 'vitest'
import { analyzeVideo, AnalyzeError, type AnalyzeHandlers } from './analyzeClient'
import type { AnalyzeResponse } from './types'

const result: AnalyzeResponse = {
  transcriptId: 't',
  sourceType: 'youtube',
  categories: [],
  expiresInSeconds: 1800,
  llm: {},
  videoId: 'dQw4w9WgXcQ',
}

function streamOf(...chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(chunk))
      controller.close()
    },
  })
}

function sse(event: string, data: unknown): Uint8Array {
  return new TextEncoder().encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
}

function mockFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function handlers(): AnalyzeHandlers & { stages: string[] } {
  const stages: string[] = []
  return { stages, onStage: (stage) => stages.push(stage) }
}

const run = (h: AnalyzeHandlers) =>
  analyzeVideo('https://youtu.be/dQw4w9WgXcQ', h, new AbortController().signal)

afterEach(() => vi.unstubAllGlobals())

describe('analyzeVideo', () => {
  it('posts a youtube request for progress streaming', async () => {
    const fetchMock = mockFetch(new Response(streamOf(sse('result', result))))

    await run(handlers())

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:3000/analyze?stream=progress')
    expect(init.method).toBe('POST')
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    })
    expect(JSON.parse(init.body as string)).toEqual({
      type: 'youtube',
      youtubeUrl: 'https://youtu.be/dQw4w9WgXcQ',
    })
  })

  it('reports stages and returns the result', async () => {
    mockFetch(
      new Response(
        streamOf(
          sse('started', { stage: 'started', message: 'm' }),
          sse('progress', { stage: 'chunking_topics', message: 'm' }),
          sse('completed', { stage: 'completed', message: 'm' }),
          sse('result', result),
        ),
      ),
    )
    const h = handlers()

    await expect(run(h)).resolves.toEqual(result)
    expect(h.stages).toEqual(['started', 'chunking_topics', 'completed'])
  })

  it('decodes multibyte text split across chunks', async () => {
    const bytes = sse('result', { ...result, transcriptId: '한글' })
    const split = bytes.indexOf(0xed) + 1
    mockFetch(new Response(streamOf(bytes.slice(0, split), bytes.slice(split))))

    const response = await run(handlers())

    expect(response.transcriptId).toBe('한글')
  })

  it('throws an SSE error event as AnalyzeError', async () => {
    mockFetch(
      new Response(
        streamOf(sse('error', { code: 'TRANSCRIPT_UNAVAILABLE', statusCode: 502, message: 'raw' })),
      ),
    )

    await expect(run(handlers())).rejects.toMatchObject({ code: 'TRANSCRIPT_UNAVAILABLE' })
  })

  it('throws the error envelope of a non-2xx response', async () => {
    mockFetch(
      new Response(JSON.stringify({ error: { code: 'INVALID_YOUTUBE_URL', message: 'bad' } }), {
        status: 400,
      }),
    )

    await expect(run(handlers())).rejects.toMatchObject({ code: 'INVALID_YOUTUBE_URL' })
  })

  it('reports a non-2xx response that is not an envelope', async () => {
    mockFetch(new Response('<html>Bad gateway</html>', { status: 502 }))

    await expect(run(handlers())).rejects.toMatchObject({ code: 'HTTP_502' })
  })

  it('reports a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(run(handlers())).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })

  it('reports a stream that ends without a result', async () => {
    mockFetch(new Response(streamOf(sse('started', { stage: 'started', message: 'm' }))))

    await expect(run(handlers())).rejects.toMatchObject({ code: 'MISSING_RESULT' })
  })

  it('lets an abort propagate untouched', async () => {
    const abort = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abort))

    const error = await run(handlers()).catch((caught) => caught)

    expect(error).toBe(abort)
    expect(error).not.toBeInstanceOf(AnalyzeError)
  })
})
