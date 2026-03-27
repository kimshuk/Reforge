---
name: Backend analyze response shape
description: The actual JSON structure returned from POST /analyze when a YouTube URL is submitted — confirmed from sample.json
type: reference
---

`/sample.json` in the repo root is a real example of the response from `POST /analyze`.

**Shape:**
```json
{
  "transcriptId": "<uuid>",
  "sourceType": "youtube",
  "videoId": "<youtube-video-id>",
  "expiresInSeconds": 3600,
  "categories": [
    {
      "title": "<category title>",
      "keywords": [
        {
          "term": "<keyword>",
          "brief": "<one-sentence label>",
          "level1": "<plain surface summary>",
          "level2": "<context/framing>",
          "level3": "<richest full insight>",
          "source": {
            "type": "youtube",
            "ref": "https://www.youtube.com/watch?v=<id>&t=<seconds>s"
          }
        }
      ]
    }
  ]
}
```

**Notes:**
- `level1`–`level3` are a drill-down: level1 is the shortest summary, level3 is the most detailed.
- `source.ref` is a timestamped YouTube deep-link to where the concept appears in the video.
- `level2`, `level3`, and `source.ref` are currently unused in the iOS UI.
- The iOS `AnalyzeModels.swift` types map directly to this shape.
