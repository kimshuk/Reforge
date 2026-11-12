import { progressFor, stageLabel } from '../hooks/analyzeState'

export function Progress({ stage }: { stage: string }) {
  const progress = progressFor(stage)
  return (
    <section className="progress" role="status" aria-live="polite">
      <p className="progress-label">{stageLabel(stage)}</p>
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${progress ? (progress.current / progress.total) * 100 : 50}%` }}
        />
      </div>
    </section>
  )
}
