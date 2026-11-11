import { describe, expect, it } from 'vitest'
import { clipsReducer, type ClipsState } from './clipsState'

const empty: ClipsState = {}

describe('clipsReducer', () => {
  it('adds a clip at level 1', () => {
    expect(clipsReducer(empty, { type: 'toggle', id: 'a' })).toEqual({ a: 1 })
  })

  it('keeps equal-term keywords separate because identity is the id', () => {
    const state = clipsReducer(clipsReducer(empty, { type: 'toggle', id: 'a' }), {
      type: 'toggle',
      id: 'b',
    })
    expect(Object.keys(state)).toEqual(['a', 'b'])
  })

  it('removes a selected clip when toggled again', () => {
    expect(clipsReducer({ a: 2 }, { type: 'toggle', id: 'a' })).toEqual({})
  })

  it('steps a clip level and stops at 3', () => {
    expect(clipsReducer({ a: 1 }, { type: 'more', id: 'a' })).toEqual({ a: 2 })
    expect(clipsReducer({ a: 3 }, { type: 'more', id: 'a' })).toEqual({ a: 3 })
  })

  it('ignores more for an unselected clip', () => {
    expect(clipsReducer(empty, { type: 'more', id: 'a' })).toBe(empty)
  })

  it('clears all clips', () => {
    expect(clipsReducer({ a: 1 }, { type: 'clear' })).toEqual({})
  })
})
