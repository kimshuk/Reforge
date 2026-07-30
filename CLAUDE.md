# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Reforge is a YouTube video analysis app. Users paste a YouTube URL, the FastAPI backend fetches the transcript, analyzes it with the configured LLM provider, persists durable analysis artifacts, and returns a compatible categories/keywords response. The iOS client displays results in expandable chip layouts with real-time streaming progress.

## Repository Layout

```
ios/             — SwiftUI iOS app (Xcode project: NoteApp.xcodeproj)
backend-fastapi/ — Active FastAPI server
backend-nest/    — Legacy NestJS server retained during migration validation
```

## Development Commands

**iOS:**
```bash
open ios/NoteApp.xcodeproj   # Open in Xcode, then Cmd+R to run
```

**Backend:**
```bash
cd backend-fastapi
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 3000
```

**Full backend stack:**
```bash
docker compose up
```

This starts `backend-fastapi`, Postgres, and Redis.

**Local backend without Docker requires Python 3.12+** and the dependencies from `backend-fastapi/pyproject.toml`.

**Backend URL config** (iOS): set `NOTEAPP_BACKEND_BASE_URL` env var, or add to `ios/.env`. Falls back to `http://localhost:3000`.

## iOS Architecture

MVVM with a protocol-based service layer:

- **`App/`** — `@main` entry point and root SwiftUI navigation
- **`Core/Networking/`** — Service protocols + implementations, models, config
  - `AnalyzeService` (protocol) / `URLSessionAnalyzeService` — streams POST `/analyze` via SSE using `URLSession.bytes(for:)`
  - `YouTubeOEmbedService` — checks video availability and auto-fills title
  - `AppConfig` — reads backend URL from env/Info.plist
  - `AnalyzeModels` — all Codable request/response types
- **`Features/Home/`** — The only feature module
  - `HomeViewModel` (`@MainActor`, `ObservableObject`) — all state and business logic
  - `HomeView` — SwiftUI view, reads from ViewModel
  - `AnalyzeResultView` — displays categories with expandable keyword chips

Services are injected via initializers, making them swappable. `HomeViewModel` owns both services.

## Backend Architecture

FastAPI app with SSE streaming on the main endpoint:

- `POST /analyze` — accepts `{ type: "youtube", youtubeUrl, title }`, streams Server-Sent Events with progress events during processing, then a final `result` event containing the compatible JSON payload
- `GET /transcript/:id` — retrieves a stored transcript
- `GET /health` — health check

Pipeline: request parsing → YouTube transcript fetch → transcript sanitizing and stable segment creation → TopicChunk boundary extraction → CandidateClipping extraction → coverage review → SQLAlchemy persistence → compatible JSON response.

### Category and Keyword Contract

- A keyword is a concrete concept, product, person, entity, claim, or other reusable item mentioned in the transcript. Every keyword must include its own source reference and YouTube timestamp.
- A category is a semantic group of related keywords, such as `OpenAI` grouping `ChatGPT`, `Codex`, and `Sam Altman`. Categories do not have source timestamps.
- Internal `TopicChunk` records are time-bounded transcript sections used for extraction and grounding. They are not output categories and their titles must not be promoted to fallback keywords.
- Output categories may group keywords extracted from different topic chunks and timestamps. Do not return categories with empty `keywords` arrays.
- Preserve keyword-level source grounding when grouping. A category title describes the group; it does not identify a specific moment in the video.
- Keyword identity is contextual-occurrence based. Equal display terms from different source ranges remain separate records when their claims, explanations, mechanisms, implications, risks, or examples differ.
- Collapse only accidental duplicate extraction records with both the same normalized term and the same resolved source segment range. Never merge equal or semantically similar terms across timestamps.
- Every retained occurrence keeps its own `candidateClippingId`, explanation ladder, and occurrence-local source references, and belongs to exactly one category. Grouping assigns existing occurrence IDs only; it may not invent, omit, rewrite, merge, or duplicate them.
- Clients must use `candidateClippingId`, not `term`, as keyword identity. Duplicate display terms are valid within one category.
- External explanation evidence is occurrence-local and additive. `level2CitationIds` and `level3CitationIds` resolve only against that keyword's `externalSources`; transcript `source`/`sources` remain unchanged. Adaptive retrieval is OpenAI-only and disabled by default.

Postgres is the durable source of truth for sources, transcripts, transcript segments, analysis runs, topic chunks, candidate clippings, coverage warnings, and eval runs. Redis is scoped to cache/coordination uses.

Error envelope shape: `{ error: { code, message } }` — the iOS client maps specific `code` strings (e.g. `TRANSCRIPT_UNAVAILABLE`, `OPENAI_CONTEXT_LENGTH_EXCEEDED`) to user-facing messages in `AnalyzeServiceError`.

## Behavioral Guidelines

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## Coding Principles: Examples and Common Mistakes

Real-world examples of what LLMs commonly do wrong and how to fix it.

### 1. Think Before Coding

#### Hidden Assumptions

**User request:** "Add a feature to export user data"

**❌ Wrong — silently assumes scope, format, fields, file location:**

```python
def export_users(format='json'):
    users = User.query.all()
    if format == 'json':
        with open('users.json', 'w') as f:
            json.dump([u.to_dict() for u in users], f)
    elif format == 'csv':
        with open('users.csv', 'w') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'email', 'name'])
            writer.writeheader()
            writer.writerows([u.to_dict() for u in users])
    return f"Exported {len(users)} users"
```

**✅ Right — surface assumptions before writing code:**

```
Before implementing, I need to clarify:

1. Scope: Export all users or a filtered subset? (privacy implications)
2. Format: Download in browser, background job with email, or API endpoint?
3. Fields: Which fields? (some may be sensitive)
4. Volume: How many users typically? (affects approach)

Simplest interpretation: API endpoint returning paginated JSON.
What's your preference?
```

#### Multiple Interpretations

**User request:** "Make the search faster"

**❌ Wrong — picks one interpretation silently, ships 200 lines of optimization:**

**✅ Right — surface the options:**

```
"Make the search faster" could mean:

1. Faster response time (< 100ms) → database indexes, caching
2. More concurrent searches (throughput) → async, connection pooling
3. Faster perceived speed (UX) → show partial results, progressive loading

Current search takes ~500ms. Which matters most?
```

---

### 2. Simplicity First

#### Over-abstraction

**User request:** "Add a function to calculate discount"

**❌ Wrong — Strategy pattern, ABC, dataclass, DiscountCalculator, 50+ lines for one calculation:**

**✅ Right:**

```python
def calculate_discount(amount: float, percent: float) -> float:
    return amount * (percent / 100)
```

Add complexity only when you actually have multiple discount types.

#### Speculative Features

**User request:** "Save user preferences to database"

**❌ Wrong — adds caching, validation, merge mode, notification hooks nobody asked for:**

**✅ Right:**

```python
def save_preferences(db, user_id: int, preferences: dict):
    db.execute(
        "UPDATE users SET preferences = ? WHERE id = ?",
        (json.dumps(preferences), user_id)
    )
```

Add caching when performance is measured as a problem. Add validation when bad data appears.

---

### 3. Surgical Changes

#### Drive-by Refactoring

**User request:** "Fix the bug where empty emails crash the validator"

**❌ Wrong — also "improves" email validation, adds username validation, rewrites comments, adds docstring:**

**✅ Right — only touch the empty-email crash:**

```diff
  def validate_user(user_data):
      # Check email format
-     if not user_data.get('email'):
+     email = user_data.get('email', '')
+     if not email or not email.strip():
          raise ValueError("Email required")
      
      # Basic email validation
-     if '@' not in user_data['email']:
+     if '@' not in email:
          raise ValueError("Invalid email")
      
      # Check username
      if not user_data.get('username'):
          raise ValueError("Username required")
      
      return True
```

Every changed line traces directly to the bug report.

#### Style Drift

**User request:** "Add logging to the upload function"

**❌ Wrong — also changes quote style, adds type hints, rewrites boolean logic, reformats whitespace:**

**✅ Right — add logging, match existing style:**

```diff
+ import logging
+ logger = logging.getLogger(__name__)
+ 
  def upload_file(file_path, destination):
+     logger.info(f'Starting upload: {file_path}')
      try:
          with open(file_path, 'rb') as f:
              data = f.read()
          response = requests.post(destination, files={'file': data})
          if response.status_code == 200:
+             logger.info(f'Upload successful: {file_path}')
              return True
          else:
+             logger.error(f'Upload failed: {file_path}, status={response.status_code}')
              return False
      except Exception as e:
-         print(f"Error: {e}")
+         logger.exception(f'Upload error: {file_path}')
          return False
```

Single quotes, no type hints, same boolean pattern — matches what was already there.

---

### 4. Goal-Driven Execution

#### Vague vs. Verifiable

**User request:** "Fix the authentication system"

**❌ Wrong — "I'll review, identify issues, make improvements, test changes" — no success criteria:**

**✅ Right — define what done looks like:**

```
What specific issue are we solving? If it's "users stay logged in after password change":

1. Write test: Change password → verify old session invalidated
   Verify: Test fails (reproduces bug)
2. Implement: Invalidate sessions on password change
   Verify: Test passes
3. Check edge cases: multiple active sessions, concurrent changes
   Verify: Additional tests pass
4. Verify no regression: existing auth tests still pass

What's the specific issue you're seeing?
```

#### Test-First Bug Fixes

**User request:** "The sorting breaks when there are duplicate scores"

**❌ Wrong — immediately changes sort logic without confirming the bug exists:**

```python
def sort_scores(scores):
    return sorted(scores, key=lambda x: (-x['score'], x['name']))
```

**✅ Right — reproduce first, then fix:**

```python
# 1. Write a test that reproduces the bug
def test_sort_with_duplicate_scores():
    scores = [
        {'name': 'Alice', 'score': 100},
        {'name': 'Bob', 'score': 100},
        {'name': 'Charlie', 'score': 90},
    ]
    result = sort_scores(scores)
    # Run 10 times — fails with inconsistent ordering for ties
    assert result == [
        {'name': 'Alice', 'score': 100},
        {'name': 'Bob', 'score': 100},
        {'name': 'Charlie', 'score': 90},
    ]

# 2. Fix with stable sort
def sort_scores(scores):
    return sorted(scores, key=lambda x: (-x['score'], x['name']))
```

---

### Anti-Patterns Summary

| Principle | Common Mistake | Fix |
|-----------|---------------|-----|
| Think Before Coding | Silently assumes format, fields, scope | List assumptions, ask before implementing |
| Simplicity First | Strategy pattern for a single calculation | One function until complexity is actually needed |
| Surgical Changes | Reformats quotes and adds type hints while fixing a bug | Only change lines that address the reported issue |
| Goal-Driven | "I'll review and improve the code" | "Write test for bug X → make it pass → verify no regressions" |

The "overcomplicated" examples aren't obviously wrong — they follow real design patterns. The problem is **timing**: complexity added before it's needed makes code harder to understand, introduces more bugs, and is harder to test. Simple code that solves today's problem can always be refactored when complexity is actually needed.

## Key Implementation Details

- **SSE parsing** in `URLSessionAnalyzeService`: reads chunked bytes, buffers lines, parses `data:` prefixes. Handles concatenated JSON objects in a single chunk.
- **`PillFlowLayout`**: custom SwiftUI `Layout` protocol implementation for wrapping keyword pill views.
- **`KeyboardObserver`**: tracks keyboard height via `UIResponder` notifications for floating UI adjustments.
- **Streaming progress states**: `HomeViewModel.AnalysisState` enum drives UI during the fetch→sanitize→analyze pipeline.
- **No test targets** are currently configured on either iOS or backend.
