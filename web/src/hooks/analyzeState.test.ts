import { describe, expect, it } from 'vitest'
import type { AnalyzeResponse } from '../api/types'
import { analyzeReducer, idleState, progressFor, stageLabel } from './analyzeState'

const result = { categories: [] } as unknown as AnalyzeResponse

describe('analyzeReducer', () => {
  it('moves from idle to streaming', () => {
    expect(analyzeReducer(idleState, { type: 'start' })).toEqual({
      status: 'streaming',
      stage: 'started',
    })
  })

  it('tracks the current stage', () => {
    const state = analyzeReducer(idleState, { type: 'start' })
    expect(analyzeReducer(state, { type: 'stage', stage: 'chunking_topics' })).toEqual({
      status: 'streaming',
      stage: 'chunking_topics',
    })
  })

  it('ignores a late stage after finishing', () => {
    const done = analyzeReducer(idleState, { type: 'result', result })
    expect(analyzeReducer(done, { type: 'stage', stage: 'completed' })).toBe(done)
  })

  it('stores results and errors', () => {
    expect(analyzeReducer(idleState, { type: 'result', result })).toEqual({
      status: 'result',
      result,
    })
    expect(analyzeReducer(idleState, { type: 'error', message: 'No' })).toEqual({
      status: 'error',
      message: 'No',
    })
  })

  it('resets to idle', () => {
    const done = analyzeReducer(idleState, { type: 'error', message: 'No' })
    expect(analyzeReducer(done, { type: 'reset' })).toBe(idleState)
  })
})

describe('stageLabel', () => {
  it('uses friendly labels', () => {
    expect(stageLabel('chunking_topics')).toBe('Finding topics…')
  })

  it('shows unknown stages raw', () => {
    expect(stageLabel('brand_new_stage')).toBe('brand_new_stage')
  })
})

describe('progressFor', () => {
  it('counts completed stages by order', () => {
    expect(progressFor('started')?.current).toBe(1)
    expect(progressFor('completed')?.current).toBe(progressFor('completed')?.total)
  })

  it('returns null for unknown stages so the stepper can hold still', () => {
    expect(progressFor('brand_new_stage')).toBeNull()
  })
})
