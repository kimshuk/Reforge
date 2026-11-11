import { useCallback, useEffect, useReducer, useRef } from 'react'
import { AnalyzeError, analyzeVideo } from '../api/analyzeClient'
import { analyzeReducer, idleState } from './analyzeState'

export function useAnalyze() {
  const [state, dispatch] = useReducer(analyzeReducer, idleState)
  const controller = useRef<AbortController | null>(null)

  const reset = useCallback(() => {
    // Aborting disconnects the stream, which also cancels the paid backend run.
    controller.current?.abort()
    controller.current = null
    dispatch({ type: 'reset' })
  }, [])

  const analyze = useCallback(async (youtubeUrl: string) => {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    dispatch({ type: 'start' })
    try {
      const result = await analyzeVideo(
        youtubeUrl,
        { onStage: (stage) => dispatch({ type: 'stage', stage }) },
        current.signal,
      )
      if (!current.signal.aborted) dispatch({ type: 'result', result })
    } catch (error) {
      if (current.signal.aborted) return
      const message = error instanceof AnalyzeError ? error.message : 'Something went wrong.'
      dispatch({ type: 'error', message })
    }
  }, [])

  useEffect(() => () => controller.current?.abort(), [])

  return { state, analyze, reset }
}
