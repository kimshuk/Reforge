# Adaptive Citation-Backed Explanation Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add best-effort, occurrence-local explanation enrichment that uses transcript context first and OpenAI web search only when external evidence materially improves `level2` or `level3`.

**Architecture:** Candidate extraction remains the source of a valid transcript-only fallback. A chunk-batched planner identifies explanatory gaps, a bounded per-occurrence OpenAI search adapter gathers URL-cited evidence, and structured synthesis plus review produces additive enrichment. External sources are persisted and serialized separately from transcript timestamps; any enrichment failure falls back for that occurrence without failing analysis.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, PostgreSQL, httpx, OpenAI Responses API web search, pytest, Swift 5, SwiftUI, XCTest.

## Global Constraints

- Keyword identity remains contextual-occurrence based and uses `candidateClippingId`, never `term`.
- `source` and `sources` remain transcript-only occurrence provenance.
- `externalSources`, `level2CitationIds`, and `level3CitationIds` are additive compatibility fields and default to empty arrays.
- `level1` remains unchanged, context-independent, and exactly one sentence.
- `level2` remains 2-3 sentences; `level3` remains 3-5 sentences; levels stay distinct and progressively more detailed.
- External information may clarify or expand the occurrence but may not replace, merge, fact-check, or silently correct the speaker's claim.
- At most three unique external sources may be retained per occurrence.
- OpenAI is the only retrieval-enabled provider in the first release; Gemini and Claude return transcript-only explanations.
- Enrichment is best-effort and must never turn an otherwise valid analysis into a 5xx response.
- Planning is chunk-batched. Retrieval calls are per occurrence with concurrency limited to three so OpenAI URL-citation text ranges cannot be attributed to the wrong keyword.
- The feature ships behind `EXPLANATION_ENRICHMENT_ENABLED=false` and can be rolled back without changing occurrence identity or response compatibility.
- Do not log transcript excerpts, generated explanations, search snippets, API keys, or complete external URLs with query parameters.

---

### Task 0: Commit The Existing Candidate Validation Baseline

**Files:**
- Verify: `backend-fastapi/app/llm.py`
- Verify: `backend-fastapi/tests/test_llm_validation.py`

**Interfaces:**
- Consumes: the current uncommitted aggregate candidate-validation changes.
- Produces: a clean baseline where candidate retries receive all ladder violations across all candidates.

- [ ] **Step 1: Inspect the existing changes and confirm scope**

Run:

```bash
git diff -- backend-fastapi/app/llm.py backend-fastapi/tests/test_llm_validation.py
git diff --check
```

Expected: only aggregate semantic validation, bounded correction retry, and their tests are present; no enrichment behavior exists.

- [ ] **Step 2: Verify the focused regression suite**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_llm_validation.py -q
.venv/bin/ruff check app/llm.py tests/test_llm_validation.py
```

Expected: all focused tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Commit the baseline separately**

```bash
git add backend-fastapi/app/llm.py backend-fastapi/tests/test_llm_validation.py
git commit -m "fix: aggregate clipping validation feedback"
```

### Task 1: Add Feature Flags And Compatible API Types

**Files:**
- Modify: `backend-fastapi/app/config.py:7-20`
- Modify: `backend-fastapi/app/schemas.py:47-75`
- Modify: `backend-fastapi/tests/test_schemas.py`
- Modify: `backend-fastapi/tests/test_api.py:24-45`
- Modify: `backend-fastapi/.env.example`

**Interfaces:**
- Consumes: existing `Settings`, `AnalyzeKeyword`, and OpenAPI response registration.
- Produces: `ExternalKeywordSource`, additive citation arrays on `AnalyzeKeyword`, and enrichment configuration used by later tasks.

- [ ] **Step 1: Write failing schema and configuration tests**

Add tests equivalent to:

```python
from app.schemas import AnalyzeKeyword


def test_keyword_citation_fields_default_to_empty_arrays() -> None:
    keyword = AnalyzeKeyword.model_validate({
        "term": "Codex",
        "candidateClippingId": "occurrence-1",
        "brief": "An autonomous coding system from OpenAI",
        "level1": "Codex is an AI system that performs coding tasks.",
        "level2": "The speaker introduces Codex as an autonomous tool. They explain the work it performs.",
        "level3": "The speaker introduces Codex as an autonomous tool. They describe concrete coding work it can perform. This explains why it matters in the section.",
        "source": {"type": "youtube", "ref": "https://example.com?t=46s"},
        "sources": [{"type": "youtube", "ref": "https://example.com?t=46s"}],
    })

    assert keyword.level2CitationIds == []
    assert keyword.level3CitationIds == []
    assert keyword.externalSources == []


def test_enrichment_is_disabled_and_bounded_by_default() -> None:
    settings = Settings()
    assert settings.explanation_enrichment_enabled is False
    assert settings.explanation_enrichment_max_sources == 3
    assert settings.explanation_enrichment_max_concurrency == 3


@pytest.mark.parametrize(
    "values",
    [
        {"explanation_enrichment_max_sources": 4},
        {"explanation_enrichment_max_concurrency": 0},
    ],
)
def test_rejects_unsafe_enrichment_limits(values: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Settings(**values)
```

Extend the OpenAPI test to assert an `ExternalKeywordSource` component and the three new keyword properties.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_schemas.py tests/test_api.py -q
```

Expected: FAIL because the settings and citation fields do not exist.

- [ ] **Step 3: Add configuration and Pydantic models**

Add to `Settings`:

```python
explanation_enrichment_enabled: bool = False
explanation_enrichment_max_sources: int = 3
explanation_enrichment_max_concurrency: int = 3
```

Add field validation requiring `explanation_enrichment_max_sources` in `1..3` and `explanation_enrichment_max_concurrency` in `1..8`.

Add to `schemas.py`:

```python
class ExternalKeywordSource(BaseModel):
    citationId: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2048)


class AnalyzeKeyword(BaseModel):
    # Existing fields remain unchanged.
    level2CitationIds: list[str] = Field(default_factory=list)
    level3CitationIds: list[str] = Field(default_factory=list)
    externalSources: list[ExternalKeywordSource] = Field(default_factory=list)
```

Document in `.env.example`:

```dotenv
EXPLANATION_ENRICHMENT_ENABLED=false
EXPLANATION_ENRICHMENT_MAX_SOURCES=3
EXPLANATION_ENRICHMENT_MAX_CONCURRENCY=3
```

- [ ] **Step 4: Run focused tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_schemas.py tests/test_api.py -q
.venv/bin/ruff check app/config.py app/schemas.py tests/test_schemas.py tests/test_api.py
```

Expected: PASS and no lint errors.

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/app/config.py backend-fastapi/app/schemas.py backend-fastapi/tests/test_schemas.py backend-fastapi/tests/test_api.py backend-fastapi/.env.example
git commit -m "feat: add explanation citation contracts"
```

### Task 2: Define Enrichment Domain Types, Prompts, And Pure Validation

**Files:**
- Create: `backend-fastapi/app/explanation_validation.py`
- Create: `backend-fastapi/app/enrichment.py`
- Create: `backend-fastapi/app/enrichment_prompts.py`
- Create: `backend-fastapi/tests/test_enrichment.py`
- Modify: `backend-fastapi/app/llm.py:1-30,375-460`
- Modify: `backend-fastapi/tests/test_llm_validation.py:1-15`

**Interfaces:**
- Consumes: current language-aware ladder rules and occurrence draft fields.
- Produces:
  - `app.explanation_validation.validate_explanation_ladder(term, brief, simple, contextual, detailed)`
  - `app.explanation_validation.sentence_count(value)`
  - `EnrichmentContext`
  - `EnrichmentPlan`
  - `ResearchSource`
  - `ResearchEvidence`
  - `OccurrenceEnrichment`
  - `validate_plan_payload(value, contexts) -> list[EnrichmentPlan]`
  - `validate_synthesis_payload(value, context, evidence) -> OccurrenceEnrichment`
  - planner, synthesis, and review JSON schemas and prompt builders.

- [ ] **Step 1: Write failing pure-domain tests**

Create tests covering exact occurrence partitioning and citation integrity:

In `test_enrichment.py`, define local `context`, `plan`, `evidence`, and `synthesis` factories. Each factory must return a fully valid Task 2 dataclass or JSON payload for `K001`, using the `GOOD` ladder text from `test_llm_validation.py`; accept explicit keyword arguments to override only the field under test.

```python
def test_plan_assigns_every_occurrence_once() -> None:
    contexts = [context("K001", "Codex"), context("K002", "Codex")]
    plans = validate_plan_payload({
        "plans": [
            plan("K001", needs_research=False),
            plan("K002", needs_research=True, research_question="What mechanism is described?"),
        ]
    }, contexts)
    assert [item.keyword_id for item in plans] == ["K001", "K002"]


@pytest.mark.parametrize("citation_ids", [["C9"], ["C1", "C1"]])
def test_synthesis_rejects_unknown_or_duplicate_citations(citation_ids: list[str]) -> None:
    with pytest.raises(AppError, match="citation"):
        validate_synthesis_payload(
            synthesis(level3_citation_ids=citation_ids),
            context("K001", "Codex"),
            evidence(source_ids=["C1"]),
        )


def test_synthesis_cannot_change_level1_or_occurrence_identity() -> None:
    with pytest.raises(AppError, match="immutable"):
        validate_synthesis_payload(
            {**synthesis(), "keywordId": "K999", "simpleExplanation": "Changed."},
            context("K001", "Codex"),
            evidence(),
        )
```

Also test absolute HTTP(S) URLs, unique source IDs, no more than three sources, ladder sentence limits, and two same-term contexts remaining independent. When evidence contains sources that synthesis does not cite, the validated result must discard those unused sources rather than expose them.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_enrichment.py -q
```

Expected: collection FAIL because `app.enrichment` does not exist.

- [ ] **Step 3: Implement immutable domain records**

First move `CJK_SCRIPT_RE`, `validate_explanation_ladder`, `explanation_ladder_errors`, `sentence_count`, and their private normalization helpers from `llm.py` to `explanation_validation.py`. Import and re-export the public functions from `llm.py` so current callers and tests remain compatible. Both `llm.py` and `enrichment.py` then depend on the neutral validation module; neither imports the other for ladder rules.

Use frozen dataclasses with tuple collections:

```python
@dataclass(frozen=True)
class EnrichmentContext:
    keyword_id: str
    term: str
    kind: str
    brief: str
    simple_explanation: str
    chunk_title: str
    chunk_summary: str
    source_excerpts: tuple[str, ...]
    transcript_level2: str
    transcript_level3: str
    video_topic_outline: tuple[str, ...]


@dataclass(frozen=True)
class EnrichmentPlan:
    keyword_id: str
    level2: str
    level3: str
    needs_external_research: bool
    research_question: str
    preferred_source_class: Literal["official", "research", "reference", "current", "none"]


@dataclass(frozen=True)
class ResearchSource:
    citation_id: str
    title: str
    url: str
    supporting_text: str


@dataclass(frozen=True)
class ResearchEvidence:
    summary: str
    sources: tuple[ResearchSource, ...]


@dataclass(frozen=True)
class OccurrenceEnrichment:
    keyword_id: str
    level2: str
    level3: str
    level2_citation_ids: tuple[str, ...] = ()
    level3_citation_ids: tuple[str, ...] = ()
    external_sources: tuple[ResearchSource, ...] = ()
```

Implement strict validators that aggregate actionable errors, preserve input order, and call the existing ladder validator with the immutable draft `term`, `brief`, and `simpleExplanation`.

- [ ] **Step 4: Add strict schemas and prompts**

Define:

```python
ENRICHMENT_PLAN_SCHEMA
ENRICHMENT_SYNTHESIS_SCHEMA
ENRICHMENT_REVIEW_SCHEMA

def enrichment_plan_prompt(contexts: list[EnrichmentContext], target_language: str) -> tuple[str, str]
def enrichment_synthesis_prompt(context: EnrichmentContext, plan: EnrichmentPlan, evidence: ResearchEvidence, target_language: str) -> tuple[str, str]
def enrichment_review_prompt(context: EnrichmentContext, enrichment: OccurrenceEnrichment, evidence: ResearchEvidence, target_language: str) -> tuple[str, str]
```

The prompts must include good and bad examples and explicitly state that the topic outline is for disambiguation only, `level1` is immutable, external claims require supplied citation IDs, and contradictory evidence requires fallback rather than correction.

- [ ] **Step 5: Run tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_enrichment.py tests/test_llm_validation.py -q
.venv/bin/ruff check app/enrichment.py app/enrichment_prompts.py app/llm.py tests/test_enrichment.py
```

Expected: PASS with existing clipping validation unchanged.

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/app/explanation_validation.py backend-fastapi/app/enrichment.py backend-fastapi/app/enrichment_prompts.py backend-fastapi/app/llm.py backend-fastapi/tests/test_enrichment.py backend-fastapi/tests/test_llm_validation.py
git commit -m "feat: define adaptive enrichment contracts"
```

### Task 3: Add Structured Planner, Synthesis, And Review Calls

**Files:**
- Modify: `backend-fastapi/app/llm.py:100-290`
- Create: `backend-fastapi/tests/test_enrichment_llm.py`

**Interfaces:**
- Consumes: Task 2 schemas, prompt builders, dataclasses, and validators.
- Produces:
  - `LlmClient.plan_explanation_enrichment(contexts, target_language, options) -> list[EnrichmentPlan]`
  - `LlmClient.synthesize_explanation_enrichment(context, plan, evidence, target_language, options) -> OccurrenceEnrichment`
  - `LlmClient.review_explanation_enrichment(context, enrichment, evidence, target_language, options) -> bool`

- [ ] **Step 1: Write failing LLM boundary tests**

Use a monkeypatched `_generate` to prove each public method passes the expected schema and validates returned IDs:

Define local `context()` and `plan_payload()` factories in this test module rather than importing test helpers from another test file. Use the same complete ladder and source excerpt in every valid baseline payload.

```python
@pytest.mark.asyncio
async def test_planner_returns_one_decision_per_context(monkeypatch) -> None:
    llm = LlmClient(Settings())
    calls = []

    async def generate(system, user, options, schema):
        calls.append(schema["name"])
        return json.dumps({"plans": [plan_payload("K001")]})

    monkeypatch.setattr(llm, "_generate", generate)
    plans = await llm.plan_explanation_enrichment(
        [context("K001")], "en", OPENAI_OPTIONS
    )
    assert plans[0].keyword_id == "K001"
    assert calls == ["explanation_enrichment_plan"]
```

Add tests for unknown/missing IDs, invalid synthesis citation mappings, review rejection, and provider errors propagating to the orchestrator boundary.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_enrichment_llm.py -q
```

Expected: FAIL because the three methods do not exist.

- [ ] **Step 3: Implement the three methods using `_generate`**

Each method must:

1. Build its prompt with Task 2 helpers.
2. Call `_generate` with the matching strict schema.
3. Parse with a stage-specific code such as `LLM_ENRICHMENT_PLAN_INVALID_JSON`.
4. Return only validated dataclasses.

Review output is exactly:

```json
{
  "approved": true,
  "reasonCode": "supported_additive_enrichment"
}
```

Do not catch provider failures here; Task 5 owns best-effort fallback.

- [ ] **Step 4: Run tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_enrichment_llm.py tests/test_enrichment.py -q
.venv/bin/ruff check app/llm.py tests/test_enrichment_llm.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/app/llm.py backend-fastapi/tests/test_enrichment_llm.py
git commit -m "feat: add explanation planning and synthesis calls"
```

### Task 4: Implement The OpenAI Web-Search Adapter

**Files:**
- Create: `backend-fastapi/app/openai_search.py`
- Create: `backend-fastapi/tests/test_openai_search.py`

**Interfaces:**
- Consumes: `Settings.openai_api_key`, resolved LLM options, `EnrichmentContext`, and `EnrichmentPlan`.
- Produces: `OpenAIWebSearchClient.research_occurrence(context, plan, options) -> ResearchEvidence`.

- [ ] **Step 1: Write failing HTTP parsing tests**

Use `httpx.MockTransport` with a Responses API payload containing a `web_search_call` and an output message with URL citation annotations:

```python
RESPONSE = {
    "status": "completed",
    "output": [
        {"type": "web_search_call", "id": "ws_1", "status": "completed"},
        {
            "type": "message",
            "content": [{
                "type": "output_text",
                "text": "Codex documentation describes delegated coding tasks.",
                "annotations": [{
                    "type": "url_citation",
                    "start_index": 0,
                    "end_index": 55,
                    "title": "OpenAI Codex documentation",
                    "url": "https://platform.openai.com/docs/codex",
                }],
            }],
        },
    ],
}
```

Assert `C1` assignment, supporting-text extraction from annotation indices, URL deduplication, maximum-three truncation, malformed annotation rejection, and mapping of HTTP/provider errors to `AppError`.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_openai_search.py -q
```

Expected: collection FAIL because `app.openai_search` does not exist.

- [ ] **Step 3: Implement the adapter**

Implement `OpenAIWebSearchClient.__init__(settings: Settings, client: httpx.AsyncClient | None = None)` and `research_occurrence(context: EnrichmentContext, plan: EnrichmentPlan, options: dict[str, Any]) -> ResearchEvidence`. Follow the existing `LlmClient` ownership pattern: use the injected client when present and otherwise create a 120-second `httpx.AsyncClient` for the request.

POST to `/v1/responses` with:

```python
{
    "model": options["model"],
    "tools": [{"type": "web_search", "search_context_size": "medium"}],
    "tool_choice": "auto",
    "input": [
        {"role": "system", "content": SEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": occurrence_research_prompt(context, plan)},
    ],
}
```

Extract only `url_citation` annotations from `output_text`, assign deterministic `C1`-`C3` IDs in first-appearance order, normalize duplicate URLs, and retain the cited span as internal `supporting_text`. Do not treat `web_search_call.action.sources` as cited support.

Reference behavior: [OpenAI Responses API web search and URL citation annotations](https://platform.openai.com/docs/api-reference/responses-streaming/response/web_search_call?lang=curl).

- [ ] **Step 4: Run tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_openai_search.py -q
.venv/bin/ruff check app/openai_search.py tests/test_openai_search.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/app/openai_search.py backend-fastapi/tests/test_openai_search.py
git commit -m "feat: retrieve occurrence-specific web evidence"
```

### Task 5: Orchestrate Adaptive Enrichment And Fallback

**Files:**
- Create: `backend-fastapi/app/explanation_enrichment.py`
- Create: `backend-fastapi/tests/test_explanation_enrichment.py`

**Interfaces:**
- Consumes: Task 2 domain types, Task 3 `LlmClient` methods, Task 4 `OpenAIWebSearchClient`, settings, and occurrence contexts.
- Produces: `ExplanationEnricher.enrich(contexts, target_language, options) -> dict[str, OccurrenceEnrichment]`.

- [ ] **Step 1: Write failing orchestration tests**

Use fake planner, search, synthesis, and review collaborators to cover:

Define `FakeLlm`, `FakeSearch`, and `enricher_with` in the test module. `FakeLlm` records planner, synthesis, and review calls and returns constructor-provided values; `FakeSearch` records active-call count and returns constructor-provided `ResearchEvidence` or raises its configured exception. The factory must build `ExplanationEnricher` with enrichment enabled and valid OpenAI options unless a test overrides them.

```python
@pytest.mark.asyncio
async def test_skips_search_when_planner_finds_no_gap() -> None:
    enricher = enricher_with(plans=[plan("K001", needs_research=False)])
    result = await enricher.enrich([context("K001")], "en", OPENAI_OPTIONS)
    assert result["K001"].external_sources == ()
    assert enricher.search.calls == []


@pytest.mark.asyncio
async def test_search_failure_falls_back_without_raising() -> None:
    enricher = enricher_with(search_error=AppError(502, "LLM_REQUEST_FAILED", "failed"))
    result = await enricher.enrich([context("K001")], "en", OPENAI_OPTIONS)
    assert result["K001"].level2 == context("K001").transcript_level2


@pytest.mark.asyncio
async def test_duplicate_terms_are_enriched_by_occurrence_id() -> None:
    result = await enricher.enrich(
        [context("K001", term="Codex"), context("K007", term="Codex")],
        "en",
        OPENAI_OPTIONS,
    )
    assert set(result) == {"K001", "K007"}
    assert result["K001"].external_sources != result["K007"].external_sources
```

Also assert disabled configuration and non-OpenAI providers make no planner or search calls, concurrency never exceeds the configured limit, planner-only rewrites are reviewed with empty external evidence, rejected review triggers one correction attempt, a second rejection falls back, one failed occurrence does not affect siblings, and content-free observability never logs terms, excerpts, prose, or complete URLs.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_explanation_enrichment.py -q
```

Expected: collection FAIL because the orchestrator does not exist.

- [ ] **Step 3: Implement fallback-first orchestration**

Define `ExplanationEnricher.__init__(llm: LlmClient, search: OpenAIWebSearchClient, settings: Settings)` and `enrich(contexts: list[EnrichmentContext], target_language: str, options: dict[str, Any]) -> dict[str, OccurrenceEnrichment]`.

Algorithm:

1. Build transcript-only fallback results before any network call.
2. Return fallbacks immediately when disabled, provider is not OpenAI, or contexts are empty.
3. Plan once for the chunk; reject the complete plan if IDs do not partition contexts exactly once.
4. Review planner-improved transcript-only levels with empty `ResearchEvidence`; accept them only when review approves, otherwise keep the original draft.
5. Research flagged occurrences independently under `asyncio.Semaphore(max_concurrency)`.
6. If no cited evidence is returned, keep the transcript-only plan result.
7. Synthesize and review cited enrichment.
8. On review rejection, perform one synthesis correction and one final review.
9. Catch enrichment-stage `AppError`, timeout, and malformed provider output per occurrence and return fallback.

Do not catch cancellation. Re-raise `asyncio.CancelledError`.

Use `time.monotonic()` and `logging.getLogger("reforge.enrichment")` to emit one content-free completion record per chunk with planned, routed, enriched, fallback, retrieval-failure, and citation-validation-failure counts plus planner, retrieval, synthesis/review, and total milliseconds. Log only counts and durations; test with `caplog` that occurrence terms, excerpts, generated prose, and source URLs never appear.

- [ ] **Step 4: Run tests and lint**

Run:

```bash
.venv/bin/pytest tests/test_explanation_enrichment.py tests/test_enrichment.py tests/test_enrichment_llm.py tests/test_openai_search.py -q
.venv/bin/ruff check app/explanation_enrichment.py tests/test_explanation_enrichment.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend-fastapi/app/explanation_enrichment.py backend-fastapi/tests/test_explanation_enrichment.py
git commit -m "feat: orchestrate best-effort explanation enrichment"
```

### Task 6: Persist External Sources And Level Citations

**Files:**
- Create: `backend-fastapi/alembic/versions/0003_add_candidate_external_sources.py`
- Modify: `backend-fastapi/app/models.py:130-194`
- Modify: `backend-fastapi/app/store.py:200-300`
- Modify: `backend-fastapi/tests/test_category_persistence.py`
- Modify: `backend-fastapi/tests/test_postgres_category_contract.py`

**Interfaces:**
- Consumes: `dict[str, OccurrenceEnrichment]` keyed by temporary `K###` occurrence ID.
- Produces: `CandidateExternalSource`, `CandidateExternalCitation`, and an extended `TranscriptStore.save_category_graph(analysis_run_id, clippings, grouping, occurrences_by_id, enrichments_by_id)` that commits the complete graph atomically.

- [ ] **Step 1: Write failing metadata and transactional tests**

Add tests asserting:

Add a local `enriched_occurrence(keyword_id, source_ids)` helper that constructs `OccurrenceEnrichment` with a valid ladder, one `ResearchSource` per requested ID, and level 3 mappings to those IDs.

```python
def test_external_source_tables_enforce_occurrence_local_citations() -> None:
    source = Base.metadata.tables["candidate_external_sources"]
    citation = Base.metadata.tables["candidate_external_citations"]
    assert {"candidateClippingId", "citationId", "title", "url", "sequence"} <= set(source.c)
    assert {"candidateClippingId", "externalSourceId", "level", "sequence"} <= set(citation.c)


@pytest.mark.asyncio
async def test_category_graph_persists_external_evidence_in_one_commit() -> None:
    await store.save_category_graph(
        run_id,
        [occurrence],
        grouping,
        {"K001": occurrence},
        {"K001": enriched_occurrence("K001", source_ids=["C1"])},
    )
    assert session.commit_count == 1
    assert any(isinstance(item, CandidateExternalSource) for item in session.added)
    assert any(isinstance(item, CandidateExternalCitation) for item in session.added)
```

Extend the real PostgreSQL contract test to reject a citation whose external source belongs to another candidate.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_category_persistence.py tests/test_postgres_category_contract.py -q
```

Expected: FAIL because migration, models, and method argument do not exist. The PostgreSQL test may skip without `TEST_DATABASE_URL`.

- [ ] **Step 3: Add migration and ORM models**

Create both tables without altering legacy tables. Use UUID primary keys, `ON DELETE CASCADE`, check `level IN (2, 3)`, unique `(candidateClippingId, citationId)`, unique `(candidateClippingId, sequence)`, and unique `(candidateClippingId, level, externalSourceId)`.

Use a composite foreign key from citation `(candidateClippingId, externalSourceId)` to source `(candidateClippingId, id)` so database constraints prevent cross-occurrence citation mappings.

- [ ] **Step 4: Extend atomic graph persistence**

Change the method signature to:

```python
async def save_category_graph(
    self,
    analysis_run_id: UUID,
    clippings: list[CandidateClipping],
    grouping: list[dict[str, Any]],
    occurrences_by_id: dict[str, CandidateClipping],
    enrichments_by_id: dict[str, OccurrenceEnrichment] | None = None,
) -> tuple[
    list[CandidateClipping],
    list[KeywordCategory],
    list[KeywordCategoryMembership],
]:
```

Flush candidate clippings first, create external source rows in deterministic source order, flush their IDs, then create level mappings. Validate enrichment keys against `occurrences_by_id` before calling `session.add_all`; rollback the complete transaction on failure.

- [ ] **Step 5: Run migration and persistence tests**

Run:

```bash
.venv/bin/pytest tests/test_category_persistence.py tests/test_postgres_category_contract.py -q
.venv/bin/alembic upgrade head
.venv/bin/ruff check app/models.py app/store.py alembic/versions/0003_add_candidate_external_sources.py tests/test_category_persistence.py
```

Expected: tests pass, migration reaches revision `0003`, and lint passes. If no local PostgreSQL is available, record the skipped integration test explicitly.

- [ ] **Step 6: Commit**

```bash
git add backend-fastapi/alembic/versions/0003_add_candidate_external_sources.py backend-fastapi/app/models.py backend-fastapi/app/store.py backend-fastapi/tests/test_category_persistence.py backend-fastapi/tests/test_postgres_category_contract.py
git commit -m "feat: persist occurrence-level external citations"
```

### Task 7: Integrate Enrichment Into Analysis And API Serialization

**Files:**
- Modify: `backend-fastapi/app/analysis.py:31-220,329-400`
- Modify: `backend-fastapi/app/main.py:50-120` only if dependency construction must be explicit.
- Modify: `backend-fastapi/tests/test_analysis.py`
- Modify: `backend-fastapi/tests/test_api.py`

**Interfaces:**
- Consumes: `ExplanationEnricher.enrich`, Task 6 persistence argument, and Task 1 response fields.
- Produces:
  - `build_enrichment_contexts(occurrences_by_id, chunks, video_outline) -> dict[UUID, list[EnrichmentContext]]`
  - enriched category persistence
  - citation fields in JSON and SSE results.

- [ ] **Step 1: Write failing pipeline tests**

Extend `ServiceLlm` or inject a fake enricher and assert:

Add a `RecordingEnricher` test double that records each chunk's `EnrichmentContext` list and returns constructor-provided `OccurrenceEnrichment` values. Extend `ServiceStore.save_category_graph` with the Task 6 optional argument and record it for assertions. Keep the existing two-timestamp Codex fixture.

```python
@pytest.mark.asyncio
async def test_analysis_enriches_duplicate_terms_without_changing_identity() -> None:
    result = await service_with_enricher(
        enrichments={
            "K001": enriched("K001", level3="The tool performs delegated coding work. It operates on concrete repository tasks. This explains its autonomous role.", source="C1"),
            "K002": enriched("K002", level3="The speaker presents commercial pressure. Autonomous coding may replace parts of existing workflows. This creates competitive risk for software companies.", source="C1"),
        }
    ).analyze(YOUTUBE_REQUEST)

    first, second = result["categories"][0]["keywords"]
    assert first["candidateClippingId"] != second["candidateClippingId"]
    assert first["source"]["ref"].endswith("t=46s")
    assert second["source"]["ref"].endswith("t=312s")
    assert first["externalSources"] != second["externalSources"]
```

Also assert exact source excerpts and chunk metadata enter each context, video outline is disambiguation-only input, fallback returns empty arrays, persistence receives the enrichment map, progress includes a non-sensitive `enriching_explanations` stage, and JSON/SSE payloads are identical.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_analysis.py tests/test_api.py -q
```

Expected: FAIL because the analysis pipeline does not call enrichment or serialize citations.

- [ ] **Step 3: Build occurrence contexts after deduplication**

After `build_grouping_occurrences`, group contexts by `clipping.topic_chunk_id`. Populate exact source excerpts from `CandidateClipping.source_refs`, current chunk title/summary, immutable draft levels, and a video outline containing only ordered chunk titles and summaries.

Do not include another occurrence's source excerpt in the context packet.

- [ ] **Step 4: Run enrichment after semantic grouping and before persistence**

Use this stage order:

```text
deduplicate occurrences
assign temporary K### IDs
group keyword IDs into semantic categories
enrich explanations best-effort
persist clippings, categories, memberships, external sources, and citations
serialize one typed result for JSON or SSE
```

For each chunk batch, call `ExplanationEnricher.enrich`; merge results by `keyword_id`; update only `CandidateClipping.level2` and `.level3`; preserve all other candidate fields.

- [ ] **Step 5: Serialize compatible citation fields**

Extend `build_analysis_result(transcript_id, source, video_id, llm_options, grouping, categories, occurrences_by_id, enrichments_by_id)` so every keyword returns:

```python
"level2CitationIds": list(enrichment.level2_citation_ids),
"level3CitationIds": list(enrichment.level3_citation_ids),
"externalSources": [
    {"citationId": item.citation_id, "title": item.title, "url": item.url}
    for item in enrichment.external_sources
],
```

When no enrichment exists, emit all three fields as empty arrays. Never copy an external URL into `source` or `sources`.

- [ ] **Step 6: Run focused and full backend verification**

Run:

```bash
.venv/bin/pytest tests/test_analysis.py tests/test_api.py -q
.venv/bin/pytest -q
.venv/bin/ruff check .
```

Expected: full suite passes; only the known optional PostgreSQL skip is acceptable.

- [ ] **Step 7: Commit**

```bash
git add backend-fastapi/app/analysis.py backend-fastapi/app/main.py backend-fastapi/tests/test_analysis.py backend-fastapi/tests/test_api.py
git commit -m "feat: enrich analysis explanations with citations"
```

### Task 8: Decode And Display Level-Specific Citations In iOS

**Files:**
- Modify: `ios/Core/Networking/AnalyzeModels.swift:63-133`
- Modify: `ios/Features/Home/HomeView.swift:280-325`
- Modify: `ios/Features/Home/AnalyzeResultView.swift:14-37`
- Modify: `ios/NoteAppTests/AnalyzeModelsTests.swift`

**Interfaces:**
- Consumes: Task 1 API fields.
- Produces:
  - `AnalyzeExternalSource`
  - citation arrays on `AnalyzeKeyword`
  - `AnalyzeKeyword.externalSources(forLevel:) -> [AnalyzeExternalSource]`
  - level-specific external links without changing keyword identity or transcript navigation.

- [ ] **Step 1: Write failing decoding and mapping tests**

Add XCTest cases equivalent to:

Define `decodeResponse(from:)` in the XCTest file using `JSONDecoder().decode(AnalyzeResponse.self, from: Data(json.utf8))`; use it for both enriched and legacy payloads.

```swift
func testDecodesLevelSpecificExternalSources() throws {
    let keyword = try decodeKeyword(from: enrichedPayload).categories[0].keywords[0]
    XCTAssertEqual(keyword.externalSources(forLevel: 2).map(\.citationId), ["C1"])
    XCTAssertEqual(keyword.externalSources(forLevel: 3).map(\.citationId), ["C1", "C2"])
    XCTAssertEqual(keyword.source.ref, "https://example.com?t=46s")
}

func testLegacyPayloadDefaultsCitationFieldsToEmpty() throws {
    let keyword = try decodeKeyword(from: legacyPayload).categories[0].keywords[0]
    XCTAssertEqual(keyword.level2CitationIds, [])
    XCTAssertEqual(keyword.level3CitationIds, [])
    XCTAssertEqual(keyword.externalSources, [])
}
```

Also retain the existing duplicate-term identity tests.

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,name=iPhone 16' test
```

Expected: FAIL because citation fields and mapping do not exist. If the named simulator is unavailable, select an installed iPhone simulator from `xcrun simctl list devices available` and record it.

- [ ] **Step 3: Add backward-compatible models**

Implement:

```swift
struct AnalyzeExternalSource: Codable, Hashable, Identifiable {
    let citationId: String
    let title: String
    let url: String
    var id: String { citationId }
}

extension AnalyzeKeyword {
    func externalSources(forLevel level: Int) -> [AnalyzeExternalSource] {
        let ids = Set(level == 2 ? level2CitationIds : level == 3 ? level3CitationIds : [])
        return externalSources.filter { ids.contains($0.citationId) }
    }
}
```

Decode `level2CitationIds`, `level3CitationIds`, and `externalSources` with `decodeIfPresent([Element].self, forKey: key) ?? []`. Keep `candidateClippingId` as identity.

- [ ] **Step 4: Display citations for the active level**

In the selected keyword explanation and `AnalyzeResultView`, render compact `Link` rows for `keyword.externalSources(forLevel: level)`. Keep the transcript `source` link visually separate and always available. Do not render raw citation IDs.

- [ ] **Step 5: Run iOS tests**

Run:

```bash
xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,name=iPhone 16' test
```

Expected: PASS with duplicate terms, legacy payloads, and enriched payloads.

- [ ] **Step 6: Commit**

```bash
git add ios/Core/Networking/AnalyzeModels.swift ios/Features/Home/HomeView.swift ios/Features/Home/AnalyzeResultView.swift ios/NoteAppTests/AnalyzeModelsTests.swift
git commit -m "feat: show level-specific explanation sources"
```

### Task 9: Document, Evaluate, And Exercise The Rollout

**Files:**
- Modify: `backend-fastapi/README.md`
- Modify: `README.md`
- Modify: `CLAUDE.md`
- Modify: `ios/LLM_CONTEXT.md`
- Create: `backend-fastapi/tests/test_enrichment_acceptance.py`

**Interfaces:**
- Consumes: the complete backend and iOS behavior.
- Produces: contributor contract, environment instructions, acceptance fixtures, and evidence for enabling the feature.

- [ ] **Step 1: Add deterministic acceptance tests**

Use mocked planner/search/synthesis boundaries to prove all five design examples:

1. A complete transcript explanation performs no search.
2. A current market occurrence gets cited `level3` detail.
3. Search failure falls back for one occurrence while siblings enrich.
4. Same-term occurrences at different timestamps retain independent citations.
5. Contradictory evidence fails review and returns transcript-only output.

Run:

```bash
cd backend-fastapi
.venv/bin/pytest tests/test_enrichment_acceptance.py -q
```

Expected before fixtures are complete: FAIL on missing acceptance behavior. Expected after completing fixtures: PASS.

- [ ] **Step 2: Update operational documentation**

Document:

```dotenv
EXPLANATION_ENRICHMENT_ENABLED=true
EXPLANATION_ENRICHMENT_MAX_SOURCES=3
EXPLANATION_ENRICHMENT_MAX_CONCURRENCY=3
```

Explain that OpenAI is required for retrieval, Gemini/Claude remain transcript-only, external citations are distinct from timestamp sources, and disabling the flag is the rollback.

- [ ] **Step 3: Run complete automated verification**

Run:

```bash
cd backend-fastapi
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/alembic upgrade head
cd ..
xcodebuild -project ios/NoteApp.xcodeproj -scheme NoteApp -destination 'platform=iOS Simulator,name=iPhone 16' test
git diff --check
```

Expected: backend tests pass, Ruff passes, Alembic reaches `0003`, iOS tests pass, and no whitespace errors exist.

- [ ] **Step 4: Run controlled live API checks**

First run with enrichment disabled and confirm empty citation arrays. Then enable the feature and restart the server:

```bash
curl -sS -X POST http://localhost:3000/analyze \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{"type":"youtube","youtubeUrl":"https://youtu.be/DGd5nbYiAis","targetLanguage":"en"}'
```

Verify:

- The request returns HTTP 200 in both modes.
- Disabled mode makes no web-search request and returns empty citation arrays.
- Enabled mode searches only planner-flagged occurrences.
- Every citation ID resolves within its keyword's `externalSources`.
- Transcript `source` remains the YouTube timestamp.
- Duplicate terms, if present, retain distinct `candidateClippingId` values.
- Retrieval failure can be simulated without converting the analysis to a 5xx response.

- [ ] **Step 5: Commit documentation and acceptance coverage**

```bash
git add backend-fastapi/README.md README.md CLAUDE.md ios/LLM_CONTEXT.md backend-fastapi/tests/test_enrichment_acceptance.py
git commit -m "docs: document adaptive explanation enrichment"
```

### Task 10: Final Review And Release Gate

**Files:**
- Review: all files changed since Task 0.

**Interfaces:**
- Consumes: all task deliverables.
- Produces: a reviewed, migration-tested, default-disabled feature ready for a pull request.

- [ ] **Step 1: Review the complete diff against the approved design**

Run:

```bash
git diff e0bc01b..HEAD --stat
git diff e0bc01b..HEAD -- backend-fastapi/app backend-fastapi/alembic backend-fastapi/tests ios README.md CLAUDE.md
```

Check occurrence isolation, additive-only behavior, per-level citation mapping, fallback boundaries, default-disabled configuration, and absence of transcript/search content in logs.

- [ ] **Step 2: Run the final verification matrix fresh**

Repeat the complete commands from Task 9 Step 3 and record exact pass, skip, and warning counts.

- [ ] **Step 3: Confirm rollout metrics are observable**

Verify safe counters/timings exist for planned occurrences, retrieval-routed occurrences, retrieval failures, enriched occurrences, transcript-only fallbacks, citation-validation failures, and stage latency. Confirm logs omit prose, snippets, keys, and complete query-string URLs.

- [ ] **Step 4: Keep the feature disabled by default**

Confirm:

```python
assert Settings().explanation_enrichment_enabled is False
```

Enable only in a controlled environment after observing latency, retrieval rate, fallback rate, and citation-validation failures.

- [ ] **Step 5: Commit any review-only corrections**

If review required changes, stage only those files and commit:

```bash
git commit -m "fix: harden explanation enrichment rollout"
```

If no corrections were needed, do not create an empty commit.
