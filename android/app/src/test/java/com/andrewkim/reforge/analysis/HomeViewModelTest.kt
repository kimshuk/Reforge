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
import okhttp3.HttpUrl
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
        assertEquals("Please enter a title.", vm.state.value.errorMessage)
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
