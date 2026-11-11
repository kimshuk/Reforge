import { formatTimestamp, secondsFromRef } from '../api/youtube'
import type { AnalyzeSource } from '../api/types'

export function Timestamp({ source }: { source: AnalyzeSource }) {
  const seconds = secondsFromRef(source.ref)
  if (seconds === null) return null
  return (
    <a className="timestamp" href={source.ref} target="_blank" rel="noreferrer">
      {formatTimestamp(seconds)}
    </a>
  )
}
