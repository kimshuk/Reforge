import { useState, type FormEvent } from 'react'
import { parseVideoId, thumbnailUrl } from '../api/youtube'

interface Props {
  busy: boolean
  onSubmit: (url: string) => void
  onClear: () => void
}

export function UrlForm({ busy, onSubmit, onClear }: Props) {
  const [url, setUrl] = useState('')
  const [showInvalid, setShowInvalid] = useState(false)
  const videoId = parseVideoId(url)

  function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    if (videoId) onSubmit(url.trim())
    else setShowInvalid(true)
  }

  function clear() {
    setUrl('')
    setShowInvalid(false)
    onClear()
  }

  return (
    <>
      <header className="header">
        <h1 className="wordmark">Reforge</h1>
        <form className="url-form" onSubmit={submit} noValidate>
          <div className="url-field">
            <input
              type="url"
              inputMode="url"
              enterKeyHint="go"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              placeholder="Paste YouTube URL"
              aria-label="YouTube URL"
              aria-invalid={showInvalid}
              value={url}
              onChange={(event) => {
                setUrl(event.target.value)
                setShowInvalid(false)
              }}
            />
            {url && (
              <button type="button" className="icon-button" aria-label="Clear" onClick={clear}>
                ✕
              </button>
            )}
          </div>
          <button type="submit" className="primary-button" disabled={busy}>
            Analyze
          </button>
        </form>
        {showInvalid && (
          <p className="field-error" role="alert">
            Enter a YouTube video link.
          </p>
        )}
      </header>
      {videoId && (
        <img className="thumbnail" src={thumbnailUrl(videoId)} alt="Video thumbnail" />
      )}
    </>
  )
}
