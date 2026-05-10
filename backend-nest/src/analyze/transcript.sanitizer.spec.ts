import { stripBracketNoise } from './transcript.sanitizer';

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
