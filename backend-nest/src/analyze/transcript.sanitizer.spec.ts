import { stripBracketNoise, normalizeText, formatTimestamp } from './transcript.sanitizer';

describe('stripBracketNoise', () => {
  it('replaces known square-bracket noise with a space', () => {
    expect(stripBracketNoise('[music] hello')).toBe('  hello');
    expect(stripBracketNoise('hello [applause]')).toBe('hello  ');
    expect(stripBracketNoise('nice [laughter] okay')).toBe('nice   okay');
  });

  it('replaces known parenthesis noise with a space', () => {
    expect(stripBracketNoise('(applause) thanks')).toBe('  thanks');
    expect(stripBracketNoise('hello (laughter) world')).toBe('hello   world');
  });

  it('preserves unrecognized brackets', () => {
    expect(stripBracketNoise('[note: this]')).toBe('[note: this]');
    expect(stripBracketNoise('(important)')).toBe('(important)');
  });

  it('matches Korean noise terms', () => {
    expect(stripBracketNoise('[박수]')).toBe(' ');
    expect(stripBracketNoise('[웃음]')).toBe(' ');
    expect(stripBracketNoise('[음악]')).toBe(' ');
  });

  it('is case-insensitive', () => {
    expect(stripBracketNoise('[Music]')).toBe(' ');
    expect(stripBracketNoise('[APPLAUSE]')).toBe(' ');
  });
});

describe('normalizeText', () => {
  it('returns empty string for non-string input', () => {
    expect(normalizeText(undefined as any)).toBe('');
    expect(normalizeText(42 as any)).toBe('');
    expect(normalizeText(null as any)).toBe('');
  });

  it('strips leading > quote markers', () => {
    expect(normalizeText('> hello')).toBe('hello');
    expect(normalizeText('>> quoted text')).toBe('quoted text');
  });

  it('collapses runs of Korean filler ㅋ to at most two', () => {
    expect(normalizeText('ㅋㅋㅋ안녕')).toBe('ㅋㅋ안녕');
    expect(normalizeText('ㅋㅋㅋㅋㅋ')).toBe('ㅋㅋ');
    expect(normalizeText('ㅋㅋ')).toBe('ㅋㅋ');
  });

  it('collapses runs of Korean filler ㅎ to at most two', () => {
    expect(normalizeText('ㅎㅎㅎ하하')).toBe('ㅎㅎ하하');
    expect(normalizeText('ㅎㅎㅎㅎ')).toBe('ㅎㅎ');
  });

  it('collapses repeated punctuation to at most two', () => {
    expect(normalizeText('nice!!!')).toBe('nice!!');
    expect(normalizeText('what???')).toBe('what??');
    expect(normalizeText('wow~~~')).toBe('wow~~');
  });

  it('normalizes internal whitespace', () => {
    expect(normalizeText('hello   world')).toBe('hello world');
  });

  it('returns empty string for decorative-only lines', () => {
    expect(normalizeText('---')).toBe('');
    expect(normalizeText('===')).toBe('');
    expect(normalizeText('...')).toBe('');
  });
});

describe('formatTimestamp', () => {
  it('formats sub-hour timestamps as MM:SS', () => {
    expect(formatTimestamp(65)).toBe('01:05');
    expect(formatTimestamp(0)).toBe('00:00');
    expect(formatTimestamp(59)).toBe('00:59');
  });

  it('formats super-hour timestamps as H:MM:SS', () => {
    expect(formatTimestamp(3661)).toBe('1:01:01');
    expect(formatTimestamp(3600)).toBe('1:00:00');
  });

  it('clamps NaN to 00:00', () => {
    expect(formatTimestamp(NaN)).toBe('00:00');
  });

  it('clamps negative values to 00:00', () => {
    expect(formatTimestamp(-5)).toBe('00:00');
  });

  it('clamps Infinity to 00:00', () => {
    expect(formatTimestamp(Infinity)).toBe('00:00');
  });
});
