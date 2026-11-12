import { describe, expect, it } from 'vitest'
import { createSseParser, type SseFrame } from './sse'

function parse(...chunks: string[]): SseFrame[] {
  const frames: SseFrame[] = []
  const parser = createSseParser((frame) => frames.push(frame))
  chunks.forEach((chunk) => parser.push(chunk))
  return frames
}

describe('createSseParser', () => {
  it('parses one frame', () => {
    expect(parse('event: progress\ndata: {"stage":"a"}\n\n')).toEqual([
      { event: 'progress', data: '{"stage":"a"}' },
    ])
  })

  it('joins a frame split across chunks', () => {
    expect(parse('event: pro', 'gress\nda', 'ta: 1\n', '\n')).toEqual([
      { event: 'progress', data: '1' },
    ])
  })

  it('emits every frame from one chunk', () => {
    expect(parse('event: a\ndata: 1\n\nevent: b\ndata: 2\n\n')).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
    ])
  })

  it('joins multiple data lines with a newline', () => {
    expect(parse('data: 1\ndata: 2\n\n')).toEqual([{ event: 'message', data: '1\n2' }])
  })

  it('accepts CRLF line endings', () => {
    expect(parse('event: a\r\ndata: 1\r\n\r\n')).toEqual([{ event: 'a', data: '1' }])
  })

  it('ignores comments and frames without data', () => {
    expect(parse(': keep-alive\n\nevent: a\n\n')).toEqual([])
  })

  it('does not emit an unterminated frame', () => {
    expect(parse('event: a\ndata: 1\n')).toEqual([])
  })
})
