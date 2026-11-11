export interface SseFrame {
  event: string
  data: string
}

export function createSseParser(onFrame: (frame: SseFrame) => void) {
  let buffer = ''
  let event = 'message'
  let dataLines: string[] = []

  function dispatch() {
    if (dataLines.length > 0) {
      onFrame({ event, data: dataLines.join('\n') })
    }
    event = 'message'
    dataLines = []
  }

  function readLine(line: string) {
    if (line === '') {
      dispatch()
    } else if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).replace(/^ /, ''))
    }
  }

  return {
    push(chunk: string) {
      buffer += chunk
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      lines.forEach((line) => readLine(line.replace(/\r$/, '')))
    },
  }
}
