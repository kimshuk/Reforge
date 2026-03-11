---
name: generate-daily-todo
description: "Analyze raw daily work notes and turn them into three sections: tasks completed today, pending or in-progress work, and a prioritized todo list for tomorrow. Use when Codex is given informal work logs, standup notes, end-of-day notes, or bullet-point updates and needs to produce a concise engineering-style task summary without inventing unrelated work."
---

# Generate Daily Todo

## Overview

Convert raw work-log notes into a compact execution summary for the next day.
Extract only tasks grounded in the provided notes and infer continuation work conservatively.

## Workflow

1. Read the notes and identify concrete actions that were clearly finished.
2. Identify work that is explicitly unfinished or obviously still active.
3. Infer the next logical engineering steps only when they directly follow from the work described.
4. Return the exact output format below.

## Extraction Rules

- Treat explicit past-tense implementation or fix statements as completed tasks.
- Treat investigation, refactor, debug, follow-up, and "need to" statements as pending or in progress unless the notes clearly say they were finished.
- If a task appears incomplete, start it with `Continue` when that phrasing fits naturally.
- Keep phrasing concise, concrete, and engineering-oriented.
- Do not add unrelated project work, meetings, or speculative tasks.
- Prefer one task per bullet; merge duplicates instead of repeating them.

## Prioritization Rules

- Put blocking or operational issues first.
- Put unfinished implementation/refactor work next.
- Add obvious validation or test follow-up last when it directly follows from completed implementation work.
- Keep the tomorrow list short; four items is a good default upper bound unless the user asks for more.

## Output Format

Return exactly this structure:

```text
TODAY_COMPLETED
- task
- task

PENDING_OR_IN_PROGRESS
- task
- task

TOMORROW_TODO
1. high priority task
2. task
3. task
4. optional task
```

## Example Mapping

Input note:

```text
- Fixed youtube transcript module bug
- Investigated staging error
- Added option1 logic to transcript pipeline
- Need to refactor prompt builder
```

Expected output style:

```text
TODAY_COMPLETED
- Fix bug in YouTube transcript module
- Implement option1 logic in transcript pipeline

PENDING_OR_IN_PROGRESS
- Continue investigating staging error
- Continue refactoring prompt builder

TOMORROW_TODO
1. Resolve staging deployment error
2. Refactor prompt builder implementation
3. Add tests for the transcript option1 workflow
```
