import { useState } from 'react'
import type { AnalyzeCategory } from '../api/types'
import { Timestamp } from './Timestamp'

interface Props {
  categories: AnalyzeCategory[]
  selected: Record<string, unknown>
  onToggle: (id: string) => void
}

export function Categories({ categories, selected, onToggle }: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (categories.length === 0) {
    return <p className="hint">We couldn't find any keywords in this video.</p>
  }

  return (
    <section className="categories" aria-label="Categories">
      {categories.map((category) => {
        const expanded = category.categoryId === expandedId
        return (
          <div className="category" key={category.categoryId}>
            <button
              type="button"
              className="category-header"
              aria-expanded={expanded}
              onClick={() => setExpandedId(expanded ? null : category.categoryId)}
            >
              <span>{category.title}</span>
              <span className="category-count">{category.keywords.length}</span>
            </button>
            {expanded && (
              <ul className="keywords">
                {category.keywords.map((keyword) => {
                  const isSelected = keyword.candidateClippingId in selected
                  return (
                    <li className="keyword" key={keyword.candidateClippingId}>
                      <button
                        type="button"
                        className="keyword-toggle"
                        aria-pressed={isSelected}
                        onClick={() => onToggle(keyword.candidateClippingId)}
                      >
                        <span className="keyword-mark" aria-hidden="true">
                          {isSelected ? '✓' : '+'}
                        </span>
                        <span className="keyword-text">
                          <strong>{keyword.term}</strong>
                          <span className="keyword-brief">{keyword.brief}</span>
                        </span>
                      </button>
                      <Timestamp source={keyword.source} />
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        )
      })}
    </section>
  )
}
