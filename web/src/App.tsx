import { useReducer } from 'react'
import { Categories } from './components/Categories'
import { ClipsTray } from './components/ClipsTray'
import { Progress } from './components/Progress'
import { UrlForm } from './components/UrlForm'
import { clipsReducer } from './hooks/clipsState'
import { useAnalyze } from './hooks/useAnalyze'

export function App() {
  const { state, analyze, reset } = useAnalyze()
  const [clips, dispatchClips] = useReducer(clipsReducer, {})

  function start(url: string) {
    dispatchClips({ type: 'clear' })
    void analyze(url)
  }

  function clear() {
    dispatchClips({ type: 'clear' })
    reset()
  }

  return (
    <div className="app">
      <main className="content">
        <UrlForm busy={state.status === 'streaming'} onSubmit={start} onClear={clear} />
        {state.status === 'idle' && <p className="hint">Paste a YouTube link to analyze it.</p>}
        {state.status === 'streaming' && <Progress stage={state.stage} />}
        {state.status === 'error' && (
          <p className="error" role="alert">
            {state.message}
          </p>
        )}
        {state.status === 'result' && (
          <Categories
            categories={state.result.categories}
            selected={clips}
            onToggle={(id) => dispatchClips({ type: 'toggle', id })}
          />
        )}
      </main>
      {state.status === 'result' && (
        <ClipsTray
          categories={state.result.categories}
          clips={clips}
          onMore={(id) => dispatchClips({ type: 'more', id })}
          onRemove={(id) => dispatchClips({ type: 'toggle', id })}
        />
      )}
    </div>
  )
}
