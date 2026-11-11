const VIDEO_ID = /^[A-Za-z0-9_-]{11}$/

// Mirrors extract_video_id in backend-fastapi/app/youtube.py.
export function parseVideoId(input: string): string | null {
  let url: URL
  try {
    url = new URL(input.trim())
  } catch {
    return null
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return null

  const host = url.hostname.toLowerCase().replace(/^www\./, '')
  const segments = url.pathname.split('/').filter(Boolean)
  let id: string | null | undefined
  if (host === 'youtu.be') {
    id = segments[0]
  } else if (host === 'youtube.com' || host === 'm.youtube.com') {
    id = url.searchParams.get('v') ?? (segments[0] === 'shorts' ? segments[1] : null)
  }
  return id && VIDEO_ID.test(id) ? id : null
}

export function thumbnailUrl(videoId: string): string {
  return `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`
}

export function secondsFromRef(ref: string): number | null {
  try {
    const match = new URL(ref).searchParams.get('t')?.match(/^(\d+)s?$/)
    return match?.[1] ? Number(match[1]) : null
  } catch {
    return null
  }
}

export function formatTimestamp(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = String(totalSeconds % 60).padStart(2, '0')
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${seconds}`
    : `${minutes}:${seconds}`
}
