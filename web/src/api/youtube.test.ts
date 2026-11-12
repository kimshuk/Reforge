import { describe, expect, it } from 'vitest'
import { formatTimestamp, parseVideoId, secondsFromRef, thumbnailUrl } from './youtube'

const ID = 'dQw4w9WgXcQ'

describe('parseVideoId', () => {
  it.each([
    `https://www.youtube.com/watch?v=${ID}`,
    `https://youtube.com/watch?list=PL1&v=${ID}&t=4s`,
    `https://m.youtube.com/watch?v=${ID}`,
    `https://youtu.be/${ID}?feature=shared`,
    `https://www.youtube.com/shorts/${ID}`,
    `http://youtu.be/${ID}/`,
    `  https://youtu.be/${ID}  `,
  ])('accepts %s', (url) => {
    expect(parseVideoId(url)).toBe(ID)
  })

  it.each([
    '',
    'not a url',
    `ftp://youtu.be/${ID}`,
    `https://example.com/watch?v=${ID}`,
    'https://www.youtube.com/watch?v=short',
    'https://www.youtube.com/watch',
    'https://youtu.be/',
  ])('rejects %j', (url) => {
    expect(parseVideoId(url)).toBeNull()
  })
})

describe('thumbnailUrl', () => {
  it('builds the hqdefault URL', () => {
    expect(thumbnailUrl(ID)).toBe(`https://img.youtube.com/vi/${ID}/hqdefault.jpg`)
  })
})

describe('secondsFromRef', () => {
  it('reads the t parameter', () => {
    expect(secondsFromRef(`https://www.youtube.com/watch?v=${ID}&t=46s`)).toBe(46)
  })

  it('accepts a bare number', () => {
    expect(secondsFromRef(`https://www.youtube.com/watch?v=${ID}&t=46`)).toBe(46)
  })

  it('returns null without a usable timestamp', () => {
    expect(secondsFromRef(`https://www.youtube.com/watch?v=${ID}`)).toBeNull()
    expect(secondsFromRef('not a url')).toBeNull()
  })
})

describe('formatTimestamp', () => {
  it.each([
    [0, '0:00'],
    [46, '0:46'],
    [125, '2:05'],
    [3723, '1:02:03'],
  ])('formats %d as %s', (seconds, expected) => {
    expect(formatTimestamp(seconds)).toBe(expected)
  })
})
