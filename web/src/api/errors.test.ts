import { describe, expect, it } from 'vitest'
import { messageForError } from './errors'

describe('messageForError', () => {
  it('maps a known code', () => {
    expect(messageForError('TRANSCRIPT_UNAVAILABLE', 'raw')).toBe(
      "This video doesn't have a transcript we can use.",
    )
  })

  it.each([
    'LLM_CLIPPINGS_INVALID_JSON',
    'LLM_CLIPPINGS_INVALID_SOURCE_REF',
    'LLM_TOPIC_CHUNKS_INVALID_JSON',
    'LLM_CATEGORY_GROUPING_INVALID_JSON',
    'LLM_EMPTY_OUTPUT',
    'LLM_RESPONSE_INCOMPLETE',
    'LLM_REQUEST_FAILED',
    'INTERNAL_SERVER_ERROR',
  ])('hides internal detail for %s', (code) => {
    expect(messageForError(code, 'Candidate 0: Brief must contain 5-10 words')).toBe(
      "We couldn't finish analyzing this video. Please try again.",
    )
  })

  it('falls back to the server message for unknown codes', () => {
    expect(messageForError('SOMETHING_NEW', 'Server detail')).toBe('Server detail')
  })

  it('falls back to a generic line when the message is empty', () => {
    expect(messageForError('SOMETHING_NEW', '  ')).toBe('Something went wrong. Please try again.')
  })
})
