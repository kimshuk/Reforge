# Daily Tasks — 2026-04-22

## Today's 3 Tasks

- [ ] **Add "Analyze" submit button to floating bar** — The only way to trigger analysis is pressing Return on the keyboard (via `.onSubmit`), which is non-obvious; add a visible circular send/arrow button to the right of the URL field that calls `viewModel.analyze()` and appears when a valid YouTube URL is present.
- [ ] **Add "Copy notes" export for selected keywords** — Users select and drill into keywords but have no way to extract value; add a share/copy button (using `ShareLink` or `UIPasteboard`) that appears when keywords are selected and formats them as `[Category] › [Term]: [description] ([timestamp])` plain text.
- [ ] **Cache analysis results by video ID on the backend** — The same YouTube video analyzed twice triggers a full transcript fetch and OpenAI call; add an in-memory result cache keyed by `videoId` (with the same TTL as `transcriptStore`) so repeat analyses return instantly without redundant API cost.

## Context

Recent work focused on UI polish: category pill tabs, progressive keyword drill-down (level1/2/3), timestamp source links, and MM:SS display. These three tasks address the next layer of completeness — making analysis triggerable without a keyboard, making results actionable by exporting them, and making the backend efficient for repeat lookups on the same video.
