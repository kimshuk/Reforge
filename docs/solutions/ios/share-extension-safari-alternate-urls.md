---
title: Accept Safari alternate URLs for one YouTube video
date: 2026-09-28
area: ios
status: verified
---

## Problem

Safari can invoke the Share Extension with two `NSExtensionItem` values for one visible YouTube page: a canonical `www.youtube.com` URL and a mobile `m.youtube.com` URL. Requiring exactly one attachment caused `ShareInputLoader` to reject a normal Safari share before any backend request.

## Mistake and why it failed

The loader treated attachment count as the number of videos the user selected. Simulator logs disproved that assumption: one Safari share contained two `public.url` providers that resolved to the same 11-character YouTube video ID. Unit tests had only modeled one provider, so the host-specific payload shape was missed.

## Verified approach

`ios/Core/Sharing/ShareInputLoader.swift` now loads URL-only attachments, uses `YouTubeVideoIdentity` to require every URL in a multi-provider payload to identify the same video, and keeps the first URL and first non-empty title. Different video IDs and mixed non-URL attachments remain invalid. Cancellation is checked before each provider load.

`ios/NoteAppTests/ShareInputLoaderTests.swift` covers canonical/mobile alternatives, different-video rejection, mixed attachment rejection, and cancellation before the next provider. The complete iOS suite passed 76 tests on one iPhone 16 Simulator with parallel destinations disabled. A live Safari share reached `/youtube/transcript`, stored the note, and opened its My Notes detail; sharing the same video again skipped the transcript request.

## Prevention

Model Share Extension inputs as host-provided representations, not a one-attachment contract. When adding a new share host, capture provider type identifiers and decoded URL values once, then add that payload shape as a loader regression test while preserving same-content validation.
