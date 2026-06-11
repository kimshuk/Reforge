---
date: 2026-06-11
topic: python-backend-clipping-migration
---

# Python Backend Clipping Migration Requirements

## Summary

Migrate the current Nest backend toward a Python/FastAPI backend that preserves the external analyze API and SSE progress flow while introducing durable internal analysis objects for long-form source clipping. The first version keeps the frontend compatible, but internally treats each YouTube video as a source that produces topic chunks, candidate clippings, coverage review results, and analysis run metadata.

---

## Problem Frame

Reforge currently analyzes transcripts into categories and keywords. That shape is useful for the current UI, but it is too weak for long-form source work because the model can return plausible categories while missing late-video topics, side arguments, or non-obvious sections that could contain useful clippings.

The migration should improve LLM quality and developer velocity at the same time. Python is a better fit for transcript processing, model comparison, structured output validation, and prompt iteration, but the migration should not force a frontend redesign or require the product to decide upfront whether extracted material is a startup idea, investment idea, research note, learning note, or content outline.

---

## Key Decisions

- **Compatibility outside, clipping model inside.** The public analyze behavior stays compatible, while the backend stores durable source, transcript, topic chunk, candidate clipping, and analysis run artifacts.
- **Major-topic coverage, not segment accounting.** The system should represent every meaningful topic shift without forcing every transcript segment into one-to-one accounting.
- **CandidateClipping is distinct from SavedClipping.** Candidate clippings are system-generated analysis outputs; saved clippings and user decision state are deferred to a later phase.
- **One production model, lightweight comparison harness.** Production uses one configured default provider/model initially, while internal evaluation can compare providers and prompt/schema versions.
- **Keywords carry temporary compatibility semantics.** The current `keywords` response field will temporarily contain richer candidate clipping data, but internal code and storage should use CandidateClipping terminology.

---

## Actors

- A1. **Current frontend user.** Runs the existing analyze flow and expects the current compatible response shape to keep working.
- A2. **Future clipping user.** Will later save, ignore, tag, organize, and develop useful candidate clippings.
- A3. **Analysis pipeline.** Fetches, cleans, chunks, extracts, reviews, persists, and maps analysis output.
- A4. **Evaluator.** Runs model and prompt comparisons against saved transcripts and reviews quality metadata.

---

## Requirements

**External compatibility**

- R1. The Python/FastAPI backend must preserve the current external analyze API behavior for the first migration version.
- R2. The Python backend must preserve the existing SSE progress pattern, streaming meaningful pipeline stages and returning the final compatible response at completion.
- R3. The compatible response must map internal TopicChunk objects to today's categories.
- R4. The compatible response must map high-signal CandidateClipping objects to today's keywords.
- R5. Every returned compatible category and keyword must be traceable back to stable internal TopicChunk and CandidateClipping IDs, even if the frontend does not use those IDs yet.

**Durable internal analysis model**

- R6. The backend must persist Source, Transcript, TopicChunk, CandidateClipping, and AnalysisRun artifacts for each completed analysis.
- R7. Source must represent a long-form input such as a YouTube video, not just a transient request payload.
- R8. Transcript must preserve cleaned transcript text and source references needed for citation, coverage review, and later reprocessing.
- R9. TopicChunk must represent a coherent major topic shift with source timing or transcript references.
- R10. CandidateClipping must represent a system-generated candidate extracted from an analysis run, with reusable metadata such as topic, claim, mechanism, risk, trend, entity, example, question, contradiction, signal level, and source reference.
- R11. AnalysisRun must record the execution context needed to audit or compare results, including model settings, prompt version, schema version, transcript identity, validation status, and timing metadata.
- R12. The backend must keep richer CandidateClipping metadata internally even when the compatible response exposes only the subset needed by the current UI.

**Long-form source pipeline**

- R13. The analysis pipeline must fetch the transcript, clean it, split it into major topic chunks, extract candidate clippings from high-signal chunks, perform a coverage review, persist artifacts, and return the compatible response.
- R14. The chunking step must aim for coherent topic chunks rather than fixed-size text windows alone.
- R15. The extraction step must avoid deciding upfront whether a candidate clipping is a startup idea, investment idea, research note, learning note, or content outline.
- R16. The extraction step must preserve timestamps or transcript references for each candidate clipping.
- R17. Intros, sponsor reads, repetition, and personal tangents should be represented as low-signal or off-topic chunks when they are major enough to affect coverage.

**Coverage discipline**

- R18. A major topic shift is a meaningful change in the speaker's subject, argument, example set, causal mechanism, named entity focus, risk discussion, or practical implication that lasts long enough to form a coherent transcript chunk.
- R19. Every major topic shift must either produce one or more candidate clippings, be represented as a low-signal or off-topic chunk, or appear in a coverage warning if the system cannot confidently classify it.
- R20. The pipeline must include an explicit coverage review step after candidate extraction.
- R21. Coverage review must reduce the chance that late-video topics, side arguments, and non-obvious but important sections are missed.
- R22. Coverage review must not require segment-by-segment transcript accounting in this migration.

**Provider and evaluation behavior**

- R23. Production analysis must use one configured default provider/model initially.
- R24. The first production version must not expose a user-facing model picker.
- R25. Internal evaluation must allow provider/model overrides.
- R26. The comparison harness must be able to run the same transcript, chunks, prompt version, and schema version across multiple model configurations.
- R27. The comparison harness must be shaped so OpenAI, Claude, and Gemini can be compared as providers, even if production uses only one provider/model.
- R28. Evaluation metadata must include provider, model, prompt version, schema version, transcript hash, latency, estimated cost when available, validation errors, and raw output.

---

## Key Flows

- F1. Compatible YouTube analysis
  - **Trigger:** The frontend sends an analyze request for a YouTube video.
  - **Actors:** A1, A3
  - **Steps:** The backend streams progress over SSE, fetches and cleans the transcript, creates topic chunks, extracts candidate clippings, performs coverage review, persists artifacts, maps chunks and candidates into the compatible response, and emits the final result.
  - **Outcome:** The current frontend receives a compatible categories-to-keywords response while the backend retains durable clipping-oriented analysis artifacts.
  - **Covered by:** R1, R2, R3, R4, R5, R6, R13

- F2. Coverage-aware extraction
  - **Trigger:** Transcript chunking and initial clipping extraction complete.
  - **Actors:** A3
  - **Steps:** The coverage review compares major topic chunks against extracted candidates, marks low-signal or off-topic chunks, and records warnings for chunks that cannot be confidently classified.
  - **Outcome:** Major topic shifts are accounted for without requiring every transcript segment to be represented.
  - **Covered by:** R18, R19, R20, R21, R22

- F3. Internal model comparison
  - **Trigger:** An evaluator runs the comparison harness against a saved transcript or analysis fixture.
  - **Actors:** A4
  - **Steps:** The harness runs selected provider/model configurations against the same transcript, chunks, prompt version, and schema version, then stores comparable metadata and raw outputs.
  - **Outcome:** Prompt and model quality can be compared without changing the production provider path.
  - **Covered by:** R23, R25, R26, R27, R28

---

## Acceptance Examples

- AE1. **Covers R3, R4, R5.** Given a completed analysis with three topic chunks and eight high-signal candidate clippings, when the compatible response is returned, then categories correspond to topic chunks, keywords correspond to candidate clippings, and each returned item can be traced to its internal durable ID.
- AE2. **Covers R18, R19, R20.** Given a transcript that changes from market context to a founder example near the end, when extraction completes, then the founder example appears as a candidate clipping, a low-signal/off-topic chunk, or a coverage warning.
- AE3. **Covers R15, R16.** Given a high-signal chunk about a company adapting a distribution mechanism, when candidate clipping extraction runs, then the candidate is stored neutrally with source references and is not forced into startup, investment, research, or content categories.
- AE4. **Covers R23, R24, R25.** Given production configuration uses one default model, when a normal frontend analyze request runs, then the user does not choose a model; when an internal evaluation run is started, then provider/model override is available to the evaluator.
- AE5. **Covers R28.** Given an evaluation run fails output validation for one provider, when metadata is saved, then the run records provider, model, prompt version, schema version, transcript hash, latency, available cost estimate, validation errors, and raw output.

---

## Success Criteria

- The current analyze frontend can continue using the Python backend without a major redesign.
- Major topic shifts in long YouTube videos are less likely to be missed than in a single best-effort LLM extraction pass.
- Candidate clippings are durable enough for later save, ignore, tag, organize, and develop workflows to attach without another backend model migration.
- Prompt and model changes can be compared against saved transcripts using the lightweight harness.
- The backend uses CandidateClipping terminology internally instead of baking the old keyword terminology into the new product model.

---

## Scope Boundaries

Deferred for later:

- User save, ignore, tag, and organization decisions.
- SavedClipping and user-owned decision state.
- Collections, boards, and developed startup, investment, research, learning, or content artifacts.
- Full provider parity in production.
- Full job polling architecture.
- Major frontend redesign.

Outside this migration:

- Segment-by-segment transcript accounting.
- A user-facing model picker.
- Treating generated candidate clippings as already user-owned saved clippings.

---

## Dependencies / Assumptions

- The first Python backend can preserve the current external analyze contract closely enough for the existing frontend to keep working.
- The current SSE progress pattern is sufficient for the first coverage-aware pipeline, even if later versions move to a job polling or subscription model.
- One default production provider/model can meet the initial quality bar while the comparison harness gathers evidence for future provider choices.
- Stable internal IDs can be generated and retained for TopicChunk and CandidateClipping objects before the frontend depends on them.

---

## Sources / Research

- `backend-nest/src/analyze/analyze.service.ts` currently coordinates request parsing, transcript resolution, transcript caching, LLM analysis, and compatible response construction.
- `backend-nest/src/analyze/youtube.service.ts` already delegates YouTube transcript fetching to Python, which makes a Python backend migration natural.
- `backend-nest/src/llm/llm.service.ts` currently centralizes prompt execution, JSON parsing, source validation, and timestamp URL resolution.
- `backend-nest/src/transcript/transcript-store.service.ts` currently stores transcripts in memory with TTL, which is insufficient for durable analysis objects.
- `backend-nest/README.md` documents the current public API: `GET /health`, `POST /analyze`, SSE progress for analyze, and `GET /transcript/:transcriptId`.
