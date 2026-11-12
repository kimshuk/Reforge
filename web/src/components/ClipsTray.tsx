import { useState } from 'react'
import { levelText, visibleExternalSources } from '../api/keywords'
import type { AnalyzeCategory } from '../api/types'
import type { ClipsState } from '../hooks/clipsState'
import { Timestamp } from './Timestamp'

interface Props {
  categories: AnalyzeCategory[]
  clips: ClipsState
  onMore: (id: string) => void
  onRemove: (id: string) => void
}

export function ClipsTray({ categories, clips, onMore, onRemove }: Props) {
  const [open, setOpen] = useState(true)
  const count = Object.keys(clips).length
  if (count === 0) return null

  return (
    <aside className="tray" aria-label="My clips">
      <button
        type="button"
        className="tray-header"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <span>My clips ({count})</span>
        <span aria-hidden="true">{open ? '▾' : '▴'}</span>
      </button>
      {open && (
        <div className="tray-body">
          {categories.map((category) => {
            const keywords = category.keywords.filter((k) => k.candidateClippingId in clips)
            if (keywords.length === 0) return null
            return (
              <section key={category.categoryId}>
                <h2 className="tray-category">{category.title}</h2>
                {keywords.map((keyword) => {
                  const id = keyword.candidateClippingId
                  const level = clips[id] ?? 1
                  const sources = visibleExternalSources(keyword, level)
                  return (
                    <article className="clip" key={id}>
                      <div className="clip-heading">
                        <strong>{keyword.term}</strong>
                        <Timestamp source={keyword.source} />
                        <button
                          type="button"
                          className="icon-button"
                          aria-label={`Remove ${keyword.term}`}
                          onClick={() => onRemove(id)}
                        >
                          ✕
                        </button>
                      </div>
                      <p className="clip-text">{levelText(keyword, level)}</p>
                      {sources.length > 0 && (
                        <ul className="clip-sources">
                          {sources.map((source) => (
                            <li key={source.citationId}>
                              <a href={source.url} target="_blank" rel="noreferrer">
                                {source.title}
                              </a>
                            </li>
                          ))}
                        </ul>
                      )}
                      {level < 3 && (
                        <button type="button" className="text-button" onClick={() => onMore(id)}>
                          More
                        </button>
                      )}
                    </article>
                  )
                })}
              </section>
            )
          })}
        </div>
      )}
    </aside>
  )
}
