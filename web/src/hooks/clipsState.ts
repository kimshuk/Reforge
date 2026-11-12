import { nextLevel } from '../api/keywords'
import type { ExplanationLevel } from '../api/types'

// Keyed by candidateClippingId, the keyword identity. Equal terms stay separate clips.
export type ClipsState = Record<string, ExplanationLevel>

export type ClipsAction =
  | { type: 'toggle'; id: string }
  | { type: 'more'; id: string }
  | { type: 'clear' }

export function clipsReducer(state: ClipsState, action: ClipsAction): ClipsState {
  switch (action.type) {
    case 'toggle': {
      if (action.id in state) {
        const { [action.id]: _removed, ...rest } = state
        return rest
      }
      return { ...state, [action.id]: 1 }
    }
    case 'more': {
      const level = state[action.id]
      return level ? { ...state, [action.id]: nextLevel(level) } : state
    }
    case 'clear':
      return {}
  }
}
