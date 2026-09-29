package com.andrewkim.reforge.analysis

import com.andrewkim.reforge.navigation.AnalysisInputSnapshot
import com.andrewkim.reforge.network.VideoUnavailableReason
import com.andrewkim.reforge.network.YouTubeAvailability
import com.andrewkim.reforge.network.YouTubeAvailabilityChecking
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.resetMain
import kotlin.coroutines.Continuation
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class HomeViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    @Before fun setUp() { Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    @Test fun debouncedAvailabilityUsesLatestUrlAndTypedReason() = runTest(dispatcher) {
        val calls = mutableListOf<String>()
        val vm = HomeViewModel(YouTubeAvailabilityChecking {
            calls += it.toString()
            YouTubeAvailability.Unavailable(VideoUnavailableReason.RATE_LIMITED)
        }, AnalysisRunning { _, _ -> emptyResult() })
        vm.setUrl("https://youtu.be/aaaaaaaaaaa")
        advanceTimeBy(300)
        vm.setUrl(url)
        advanceTimeBy(499)
        runCurrent()
        assertTrue(calls.isEmpty())
        advanceTimeBy(1)
        runCurrent()
        assertEquals(listOf(url), calls)
        assertEquals(VideoUnavailableReason.RATE_LIMITED, vm.state.value.unavailableReason)
        assertEquals(VideoUnavailableReason.RATE_LIMITED.userMessage, vm.state.value.errorMessage)
    }

    @Test fun clearingThenReenteringSameUrlRefetchesAfterFullDebounce() = runTest(dispatcher) {
        var calls = 0
        val vm = HomeViewModel(YouTubeAvailabilityChecking {
            calls++
            YouTubeAvailability.Available("Title $calls")
        }, AnalysisRunning { _, _ -> emptyResult() })
        vm.setUrl(url)
        advanceTimeBy(500)
        runCurrent()
        assertEquals("Title 1", vm.state.value.title)
        vm.setUrl("")
        assertEquals("", vm.state.value.title)
        vm.setUrl(url)
        advanceTimeBy(499)
        runCurrent()
        assertEquals(1, calls)
        assertEquals("", vm.state.value.title)
        advanceTimeBy(1)
        runCurrent()
        assertEquals(2, calls)
        assertEquals("Title 2", vm.state.value.title)
    }

    @Test fun returningToPriorUrlWhileOtherDebouncePendingRefetches() = runTest(dispatcher) {
        val calls = mutableListOf<String>()
        val vm = HomeViewModel(YouTubeAvailabilityChecking {
            calls += it.toString()
            YouTubeAvailability.Available("Title ${calls.size}")
        }, AnalysisRunning { _, _ -> emptyResult() })
        vm.setUrl(url)
        advanceTimeBy(500)
        runCurrent()
        assertEquals("Title 1", vm.state.value.title)
        vm.setUrl("https://youtu.be/aaaaaaaaaaa")
        advanceTimeBy(250)
        vm.setUrl(url)
        advanceTimeBy(499)
        runCurrent()
        assertEquals(listOf(url), calls)
        assertEquals("", vm.state.value.title)
        advanceTimeBy(1)
        runCurrent()
        assertEquals(listOf(url, url), calls)
        assertEquals("Title 2", vm.state.value.title)
    }

    @Test fun availabilityTransportFailureDoesNotBlockAnalysis() = runTest(dispatcher) {
        var requests = 0
        val vm = HomeViewModel(YouTubeAvailabilityChecking { throw IllegalStateException("decode") },
            AnalysisRunning { _, _ -> requests++; emptyResult() })
        vm.setUrl(url)
        advanceTimeBy(500)
        runCurrent()
        assertNull(vm.state.value.unavailableReason)
        vm.setTitle("Title")
        vm.analyze()
        runCurrent()
        assertEquals(1, requests)
        assertTrue(vm.state.value.errorMessage.isEmpty())
    }

    @Test fun lateAvailabilityCannotOverwriteManualTitle() = runTest(dispatcher) {
        val pending = CompletableDeferred<YouTubeAvailability>()
        val vm = HomeViewModel(YouTubeAvailabilityChecking { pending.await() },
            AnalysisRunning { _, _ -> emptyResult() })
        vm.setUrl(url)
        advanceTimeBy(500)
        runCurrent()
        vm.setTitle("Manual title")
        pending.complete(YouTubeAvailability.Available("Late title"))
        runCurrent()
        assertEquals("Manual title", vm.state.value.title)
    }

    @Test fun manualTitleDoesNotBypassTypedUnavailable() = runTest(dispatcher) {
        val pending = CompletableDeferred<YouTubeAvailability>()
        var analyzes = 0
        val vm = HomeViewModel(YouTubeAvailabilityChecking { pending.await() },
            AnalysisRunning { _, _ -> analyzes++; emptyResult() })
        vm.setUrl(url)
        advanceTimeBy(500)
        runCurrent()
        vm.setTitle("Manual title")
        pending.complete(YouTubeAvailability.Unavailable(VideoUnavailableReason.NOT_FOUND_OR_REMOVED))
        runCurrent()
        assertEquals(VideoUnavailableReason.NOT_FOUND_OR_REMOVED, vm.state.value.unavailableReason)
        assertEquals(VideoUnavailableReason.NOT_FOUND_OR_REMOVED.userMessage, vm.state.value.errorMessage)
        vm.analyze()
        runCurrent()
        assertEquals(0, analyzes)
        assertEquals(VideoUnavailableReason.NOT_FOUND_OR_REMOVED.userMessage, vm.state.value.errorMessage)
    }

    @Test fun everyTypedUnavailableReasonSurvivesAnalyzeWithEmptyTitle() = runTest(dispatcher) {
        for (reason in VideoUnavailableReason.entries) {
            var analyzes = 0
            val vm = HomeViewModel(
                YouTubeAvailabilityChecking { YouTubeAvailability.Unavailable(reason) },
                AnalysisRunning { _, _ -> analyzes++; emptyResult() },
            )
            vm.setUrl(url)
            advanceTimeBy(500)
            runCurrent()
            assertEquals("", vm.state.value.title)
            vm.analyze()
            runCurrent()
            assertEquals(reason.userMessage, vm.state.value.errorMessage)
            assertEquals(0, analyzes)
        }
    }

    @Test fun timeoutLeavesHomeEditableWithExistingAnalysisFailureCopy() = runTest(dispatcher) {
        var requests = 0
        val vm = HomeViewModel(
            YouTubeAvailabilityChecking { YouTubeAvailability.Available("Title") },
            AnalysisRunning { _, _ -> requests++; throw AnalyzeApiError.TimedOut },
        )
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Title", url))
        runCurrent()
        assertFalse(vm.state.value.isLoading)
        assertEquals("Analysis failed on the backend. Please try again.", vm.state.value.errorMessage)
        assertEquals("", vm.state.value.loadingStage)
        assertEquals("", vm.state.value.loadingStatusMessage)
        assertNull(vm.state.value.result)
        assertEquals(1, requests)
        vm.setTitle("Edited")
        assertEquals("Edited", vm.state.value.title)
        assertEquals(1, requests)
    }

    @Test fun currentLlmCodesAndUnknownMessagesNeverExposeProviderDiagnostics() {
        val currentCodes = listOf(
            "LLM_AUTH_ERROR", "LLM_QUOTA_OR_RATE_LIMIT", "LLM_CONTEXT_LENGTH_EXCEEDED", "LLM_REQUEST_FAILED",
            "LLM_PROVIDER_NOT_CONFIGURED", "LLM_RESPONSE_INCOMPLETE", "LLM_EMPTY_OUTPUT",
            "LLM_TOPIC_CHUNKS_INVALID_JSON", "LLM_TOPIC_CHUNKS_EMPTY", "LLM_TOPIC_CHUNKS_INVALID_BOUNDARY",
            "LLM_CLIPPINGS_INVALID_JSON", "LLM_CLIPPINGS_INVALID_SOURCE_REF", "LLM_CATEGORY_GROUPING_INVALID_JSON",
            "LLM_ENRICHMENT_PLAN_INVALID_JSON", "LLM_ENRICHMENT_SYNTHESIS_INVALID_JSON",
            "LLM_ENRICHMENT_REVIEW_INVALID_JSON", "LLM_WEB_SEARCH_INVALID_RESPONSE",
            "INVALID_LLM_PROVIDER", "INVALID_LLM_MODEL", "INVALID_LLM_TEMPERATURE", "INVALID_LLM_MAX_OUTPUT_TOKENS",
            "UNKNOWN_BACKEND_CODE", "https://provider.example/private?api_key=secret",
        )
        for (code in currentCodes) {
            val message = analysisErrorMessage(AnalyzeApiError.Backend(
                502, code, "Provider https://provider.example/private?api_key=secret; stack trace: internal diagnostic",
            ))
            assertEquals(code, "Analysis failed on the backend. Please try again.", message)
            assertFalse(message.contains("https://"))
            assertFalse(message.contains("secret"))
            assertFalse(message.contains("diagnostic"))
            assertFalse(message.contains(code))
        }
        assertEquals("Backend OpenAI configuration is invalid.",
            analysisErrorMessage(AnalyzeApiError.Backend(401, "OPENAI_AUTH_ERROR", "secret")))
    }

    @Test fun snapshotClearsOldStateAndStartsOnceWithoutAvailabilityLookup() = runTest(dispatcher) {
        var checks = 0
        val requests = mutableListOf<AnalyzeRequest>()
        val pending = CompletableDeferred<AnalyzeResponse>()
        val vm = HomeViewModel(YouTubeAvailabilityChecking {
            checks++
            YouTubeAvailability.Available("Fetched")
        }, AnalysisRunning { request, _ -> requests += request; pending.await() })
        vm.setUrl("https://youtu.be/aaaaaaaaaaa")
        vm.setTitle("Old")
        vm.analyze()
        runCurrent()
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Saved", url))
        runCurrent()
        vm.analyze()
        runCurrent()
        assertEquals("Saved", vm.state.value.title)
        assertEquals(url, vm.state.value.url)
        assertEquals(0, checks)
        assertEquals(2, requests.size)
        assertEquals(AnalyzeRequest(title = "Saved", youtubeUrl = url), requests.last())
        assertTrue(vm.state.value.isLoading)
        pending.complete(emptyResult())
        runCurrent()
    }

    @Test fun staleAvailabilityAndProgressCannotOverwriteNewSnapshot() = runTest(dispatcher) {
        val available = CompletableDeferred<YouTubeAvailability>()
        val callbacks = mutableListOf<(AnalyzeProgressUpdate) -> Unit>()
        val result = CompletableDeferred<AnalyzeResponse>()
        val vm = HomeViewModel(YouTubeAvailabilityChecking { available.await() },
            AnalysisRunning { _, progress -> callbacks += progress; result.await() })
        vm.setUrl("https://youtu.be/aaaaaaaaaaa")
        advanceTimeBy(500)
        runCurrent()
        vm.setTitle("Old")
        vm.analyze()
        runCurrent()
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Saved", url))
        runCurrent()
        callbacks.first().invoke(AnalyzeProgressUpdate("late", "Late"))
        available.complete(YouTubeAvailability.Unavailable(VideoUnavailableReason.NOT_FOUND_OR_REMOVED))
        runCurrent()
        assertEquals("Saved", vm.state.value.title)
        assertNull(vm.state.value.unavailableReason)
        assertEquals("started", vm.state.value.loadingStage)
        result.complete(emptyResult())
        runCurrent()
    }

    @Test fun duplicateServerIdsKeepIndependentSelectionsAndLevelCap() = runTest(dispatcher) {
        val vm = HomeViewModel(YouTubeAvailabilityChecking { YouTubeAvailability.Available("Title") },
            AnalysisRunning { _, _ -> duplicateResult() })
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Title", url))
        runCurrent()
        val first = KeywordOccurrence(0, 0)
        val second = KeywordOccurrence(1, 0)
        vm.selectKeyword(first)
        vm.selectKeyword(second)
        repeat(5) { vm.advanceKeyword(first) }
        assertEquals(3, vm.state.value.selection.level(first))
        assertEquals(1, vm.state.value.selection.level(second))
        vm.removeKeyword(first)
        assertFalse(vm.state.value.selection.isSelected(first))
        assertTrue(vm.state.value.selection.isSelected(second))
    }

    @Test fun selectingExistingKeywordPreservesExpandedLevel() {
        val key = KeywordOccurrence(0, 0)
        val levelTwo = KeywordSelectionState().select(key).advanceLevel(key)
        assertEquals(2, levelTwo.select(key).level(key))
        val levelThree = levelTwo.advanceLevel(key)
        assertEquals(3, levelThree.select(key).level(key))
    }

    @Test fun staleCallbacksCannotWinEvenWhenFakesIgnoreCancellation() = runTest(dispatcher) {
        val checks = mutableListOf<Continuation<YouTubeAvailability>>()
        val analyses = mutableListOf<Continuation<AnalyzeResponse>>()
        val vm = HomeViewModel(
            YouTubeAvailabilityChecking { suspendCoroutine { checks += it } },
            AnalysisRunning { _, _ -> suspendCoroutine { analyses += it } },
        )
        vm.setUrl("https://youtu.be/aaaaaaaaaaa")
        advanceTimeBy(500)
        runCurrent()
        vm.setUrl(url)
        checks[0].resume(YouTubeAvailability.Available("Stale title"))
        runCurrent()
        assertEquals("", vm.state.value.title)
        advanceTimeBy(500)
        runCurrent()
        checks[1].resume(YouTubeAvailability.Available("Current title"))
        runCurrent()
        assertEquals("Current title", vm.state.value.title)

        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("First", url))
        runCurrent()
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Second", url))
        runCurrent()
        analyses[0].resume(emptyResult())
        runCurrent()
        assertNull(vm.state.value.result)
        assertTrue(vm.state.value.isLoading)
        analyses[1].resume(emptyResult())
        runCurrent()

        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Third", url))
        runCurrent()
        vm.applySnapshotAndAnalyze(AnalysisInputSnapshot("Fourth", url))
        runCurrent()
        analyses[2].resumeWithException(IllegalStateException("Stale error"))
        runCurrent()
        assertEquals("", vm.state.value.errorMessage)
        assertTrue(vm.state.value.isLoading)
        analyses[3].resume(emptyResult())
        runCurrent()
    }

    private fun emptyResult() = AnalyzeResponse("transcript", "youtube", emptyList(), 60, "dQw4w9WgXcQ")
    private fun duplicateResult(): AnalyzeResponse {
        val keyword = AnalyzeKeyword("same", "same", "term", "brief", "level one", "level two", "level three",
            AnalyzeSource("youtube", "$url&t=61"), emptyList(), emptyList(), emptyList(), emptyList())
        return AnalyzeResponse("transcript", "youtube", listOf(
            AnalyzeCategory("same", "same", "A", listOf(keyword)),
            AnalyzeCategory("same", "same", "B", listOf(keyword)),
        ), 60, "dQw4w9WgXcQ")
    }
}
