package com.andrewkim.reforge.sharing

import androidx.lifecycle.SavedStateHandle
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.Dispatchers
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ShareImportViewModelTest {
    private val input = SharedTextParser.parse("https://youtu.be/dQw4w9WgXcQ") as SharedTextResult.Valid
    private val other = SharedTextParser.parse("https://youtu.be/aaaaaaaaaaa") as SharedTextResult.Valid
    private val dispatcher = StandardTestDispatcher()

    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    @Test fun newInputCancelsOldWorkAndOldResultCannotReplaceNewCompletion() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        val old = CompletableDeferred<ShareIngestionResult>()
        ingestor.ingestBlock = {
            if (it == input) withContext(NonCancellable) { old.await() }
            else ShareIngestionResult.Saved("new")
        }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        testScheduler.runCurrent()
        viewModel.accept(other)
        testScheduler.runCurrent()
        assertEquals(ShareImportState.Completed(2, "new"), viewModel.state.value)
        old.complete(ShareIngestionResult.Saved("old"))
        advanceUntilIdle()
        assertEquals(ShareImportState.Completed(2, "new"), viewModel.state.value)
    }

    @Test fun lateOldErrorCannotReplaceNewLoading() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        val old = CompletableDeferred<Unit>()
        val latest = CompletableDeferred<ShareIngestionResult>()
        ingestor.ingestBlock = {
            if (it == input) {
                withContext(NonCancellable) { old.await() }
                throw ShareIngestionFailure.Provider
            } else latest.await()
        }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        testScheduler.runCurrent()
        viewModel.accept(other)
        testScheduler.runCurrent()
        old.complete(Unit)
        testScheduler.runCurrent()
        assertEquals(ShareImportState.Loading(2), viewModel.state.value)
        latest.complete(ShareIngestionResult.Saved("latest"))
        advanceUntilIdle()
        assertEquals(ShareImportState.Completed(2, "latest"), viewModel.state.value)
    }

    @Test fun staleErrorsAndRestorePromptsDoNotReplaceNewGeneration() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        ingestor.ingestBlock = { if (it == input) ShareIngestionResult.RestoreRequired("old") else ShareIngestionResult.Saved("new") }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        viewModel.accept(other)
        advanceUntilIdle()
        assertEquals(ShareImportState.Completed(2, "new"), viewModel.state.value)
        viewModel.acknowledgeDetailOpened(1, "old")
        assertEquals(ShareImportState.Completed(2, "new"), viewModel.state.value)
    }

    @Test fun backBeforeSaveCancelsWorkAndDoesNotComplete() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        val gate = CompletableDeferred<ShareIngestionResult>()
        ingestor.ingestBlock = { gate.await() }
        val handle = SavedStateHandle()
        val viewModel = ShareImportViewModel(ingestor, handle)
        viewModel.accept(input)
        testScheduler.runCurrent()
        viewModel.cancelImport()
        advanceUntilIdle()
        assertEquals(ShareImportState.Finished(1), viewModel.state.value)
        gate.complete(ShareIngestionResult.Saved("late"))
        advanceUntilIdle()
        assertEquals(ShareImportState.Finished(1), viewModel.state.value)
        assertEquals(ShareImportState.Finished(1), ShareImportViewModel(ingestor, handle).state.value)
    }

    @Test fun committedSuccessRemainsCompletedWhenCancelFollows() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        ingestor.ingestBlock = { ShareIngestionResult.Saved("committed") }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        advanceUntilIdle()
        assertEquals(ShareImportState.Completed(1, "committed"), viewModel.state.value)
        viewModel.cancelImport()
        assertEquals(ShareImportState.Completed(1, "committed"), viewModel.state.value)
    }

    @Test fun restoreIsSingleFlightAndCancelIgnoresLateCompletion() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        val restore = CompletableDeferred<ShareIngestionResult>()
        ingestor.ingestBlock = { ShareIngestionResult.RestoreRequired("existing") }
        ingestor.restoreBlock = { restore.await() }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        advanceUntilIdle()
        assertEquals(ShareImportState.AwaitingRestore(1, "existing"), viewModel.state.value)
        viewModel.confirmRestore()
        viewModel.confirmRestore()
        testScheduler.runCurrent()
        assertEquals(1, ingestor.restoreCalls)
        viewModel.cancelRestore()
        restore.complete(ShareIngestionResult.AlreadySaved("existing"))
        advanceUntilIdle()
        assertEquals(ShareImportState.Finished(1), viewModel.state.value)
    }

    @Test fun restoreAfterPurgeShowsApprovedStorageCopy() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        ingestor.ingestBlock = { ShareIngestionResult.RestoreRequired("deleted") }
        ingestor.restoreBlock = { throw ShareIngestionFailure.Storage }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        advanceUntilIdle()
        viewModel.confirmRestore()
        advanceUntilIdle()
        assertEquals(
            ShareImportState.Error(1, "Couldn’t save this video. Please try again."),
            viewModel.state.value,
        )
    }

    @Test fun externalRestoreOpensOriginalNote() = runTest(dispatcher) {
        val ingestor = FakeIngestor()
        ingestor.ingestBlock = { ShareIngestionResult.RestoreRequired("existing") }
        ingestor.restoreBlock = { ShareIngestionResult.AlreadySaved("existing") }
        val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
        viewModel.accept(input)
        advanceUntilIdle()
        viewModel.confirmRestore()
        advanceUntilIdle()
        assertEquals(ShareImportState.Completed(1, "existing"), viewModel.state.value)
    }

    @Test fun completionRecoversOnceAcrossRecreationAndAcknowledgement() = runTest(dispatcher) {
        val handle = SavedStateHandle()
        val ingestor = FakeIngestor()
        ingestor.ingestBlock = { ShareIngestionResult.Saved("saved") }
        val first = ShareImportViewModel(ingestor, handle)
        first.accept(input)
        advanceUntilIdle()
        val recovered = ShareImportViewModel(ingestor, handle)
        assertEquals(ShareImportState.Completed(1, "saved"), recovered.state.value)
        recovered.acknowledgeDetailOpened(1, "wrong")
        assertEquals(ShareImportState.Completed(1, "saved"), recovered.state.value)
        recovered.acknowledgeDetailOpened(1, "saved")
        assertEquals(ShareImportState.Completed(1, "saved", true), recovered.state.value)
        val acknowledged = ShareImportViewModel(ingestor, handle)
        assertEquals(ShareImportState.Completed(1, "saved", true), acknowledged.state.value)
        assertFalse((acknowledged.state.value as ShareImportState.Completed).let { !it.navigationAcknowledged })
        acknowledged.accept(other)
        advanceUntilIdle()
        assertEquals(2, (acknowledged.state.value as ShareImportState.Completed).generation)
    }

    @Test fun exactFailureCopyAndInvalidInput() = runTest(dispatcher) {
        val cases = listOf(
            ShareIngestionFailure.InvalidIdentity to "Please enter a valid YouTube URL.",
            ShareIngestionFailure.IdentityMismatch to "Please enter a valid YouTube URL.",
            ShareIngestionFailure.TranscriptUnavailable to "The video is available, but transcript is not available.",
            ShareIngestionFailure.Provider to "Transcript provider failed. Please try again.",
            ShareIngestionFailure.Storage to "Couldn’t save this video. Please try again.",
        )
        for ((failure, copy) in cases) {
            val ingestor = FakeIngestor()
            ingestor.ingestBlock = { throw failure }
            val viewModel = ShareImportViewModel(ingestor, SavedStateHandle())
            viewModel.accept(input)
            advanceUntilIdle()
            assertEquals(ShareImportState.Error(1, copy), viewModel.state.value)
        }
        val invalid = ShareImportViewModel(FakeIngestor(), SavedStateHandle())
        invalid.accept(SharedTextResult.Invalid)
        assertEquals(ShareImportState.Error(1, "Please enter a valid YouTube URL."), invalid.state.value)
    }

    private class FakeIngestor : ShareIngesting {
        var ingestBlock: suspend (SharedTextResult.Valid) -> ShareIngestionResult = {
            ShareIngestionResult.Saved("saved")
        }
        var restoreBlock: suspend (String) -> ShareIngestionResult = {
            ShareIngestionResult.AlreadySaved(it)
        }
        var restoreCalls = 0
        override suspend fun ingest(input: SharedTextResult.Valid) = ingestBlock(input)
        override suspend fun restore(noteId: String): ShareIngestionResult {
            restoreCalls++
            return restoreBlock(noteId)
        }
    }
}
