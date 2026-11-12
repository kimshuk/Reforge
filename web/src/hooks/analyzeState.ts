import type { AnalyzeResponse } from '../api/types'

export type AnalyzeState =
  | { status: 'idle' }
  | { status: 'streaming'; stage: string }
  | { status: 'result'; result: AnalyzeResponse }
  | { status: 'error'; message: string }

export type AnalyzeAction =
  | { type: 'start' }
  | { type: 'stage'; stage: string }
  | { type: 'result'; result: AnalyzeResponse }
  | { type: 'error'; message: string }
  | { type: 'reset' }

export const idleState: AnalyzeState = { status: 'idle' }

export function analyzeReducer(state: AnalyzeState, action: AnalyzeAction): AnalyzeState {
  switch (action.type) {
    case 'start':
      return { status: 'streaming', stage: 'started' }
    case 'stage':
      return state.status === 'streaming' ? { ...state, stage: action.stage } : state
    case 'result':
      return { status: 'result', result: action.result }
    case 'error':
      return { status: 'error', message: action.message }
    case 'reset':
      return idleState
  }
}

const STAGES: [stage: string, label: string][] = [
  ['started', 'Starting…'],
  ['fetching_transcript', 'Fetching transcript…'],
  ['sanitizing_transcript', 'Cleaning transcript…'],
  ['transcript_ready', 'Transcript ready…'],
  ['creating_segments', 'Preparing segments…'],
  ['chunking_topics', 'Finding topics…'],
  ['validating_chunks', 'Checking topics…'],
  ['extracting_clippings', 'Extracting keywords…'],
  ['deduplicating_occurrences', 'Removing duplicates…'],
  ['grouping_keywords', 'Grouping keywords…'],
  ['enriching_explanations', 'Adding context…'],
  ['reviewing_coverage', 'Reviewing coverage…'],
  ['storing_analysis', 'Saving…'],
  ['completed', 'Finishing…'],
]

export function stageLabel(stage: string): string {
  return STAGES.find(([name]) => name === stage)?.[1] ?? stage
}

export function progressFor(stage: string): { current: number; total: number } | null {
  const index = STAGES.findIndex(([name]) => name === stage)
  return index < 0 ? null : { current: index + 1, total: STAGES.length }
}
