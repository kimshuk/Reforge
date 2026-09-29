package com.andrewkim.reforge.sharing

import com.andrewkim.reforge.network.ApiError
import com.andrewkim.reforge.network.ShareTitleResolving
import com.andrewkim.reforge.network.YoutubeTranscriptFetching
import com.andrewkim.reforge.network.YoutubeTranscriptResponse
import com.andrewkim.reforge.notes.ContentNote
import com.andrewkim.reforge.notes.ContentNoteDraft
import com.andrewkim.reforge.notes.ContentNoteRepository
import com.andrewkim.reforge.notes.RestoreOutcome
import com.andrewkim.reforge.notes.SaveNoteOutcome
import com.andrewkim.reforge.notes.ShareNotePreparation
import java.time.Instant
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import okhttp3.HttpUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ShareIngestionCoordinatorTest {
    private val input = SharedTextParser.parse("https://youtu.be/dQw4w9WgXcQ") as SharedTextResult.Valid
    private val instant = Instant.parse("2026-09-29T00:00:00Z")

    @Test fun activePreflightDoesNotCallNetworkOrSave() = runTest {
        val fixture = Fixture()
        fixture.repository.preparation = ShareNotePreparation.Active(note())
        assertEquals(ShareIngestionResult.AlreadySaved("existing"), fixture.coordinator.ingest(input))
        assertEquals(0, fixture.transcript.calls)
        assertEquals(0, fixture.title.calls)
        assertEquals(0, fixture.repository.saves)
    }

    @Test fun trashedPreflightRequiresRestoreWithoutMutation() = runTest {
        val fixture = Fixture()
        fixture.repository.preparation = ShareNotePreparation.Trashed(note(trashed = true))
        assertEquals(ShareIngestionResult.RestoreRequired("existing"), fixture.coordinator.ingest(input))
        assertEquals(0, fixture.transcript.calls)
        assertEquals(0, fixture.title.calls)
        assertEquals(0, fixture.repository.saves)
        assertEquals(0, fixture.repository.restores)
    }

    @Test fun absentFetchesTranscriptAndMetadataConcurrentlyThenSavesThirteenFields() = runTest {
        val fixture = Fixture()
        val transcriptGate = CompletableDeferred<Unit>()
        val titleGate = CompletableDeferred<Unit>()
        fixture.transcript.beforeReturn = { transcriptGate.await() }
        fixture.title.beforeReturn = { titleGate.await() }
        fixture.title.value = "Metadata title"
        val result = async(StandardTestDispatcher(testScheduler)) { fixture.coordinator.ingest(input) }
        testScheduler.runCurrent()
        assertEquals(1, fixture.transcript.calls)
        assertEquals(1, fixture.title.calls)
        assertEquals(0, fixture.repository.saves)
        transcriptGate.complete(Unit)
        titleGate.complete(Unit)
        advanceUntilIdle()
        assertEquals(ShareIngestionResult.Saved("new"), result.await())
        val draft = requireNotNull(fixture.repository.lastDraft)
        assertEquals("youtube:dQw4w9WgXcQ", draft.sourceKey)
        assertEquals("youtube", draft.sourceType)
        assertEquals("dQw4w9WgXcQ", draft.videoId)
        assertEquals(input.sourceUrl, draft.sourceUrl)
        assertEquals(input.identity.canonicalUrl.toString(), draft.canonicalUrl)
        assertEquals("Metadata title", draft.title)
        assertEquals("transcript-1", draft.transcriptId)
        assertEquals("Transcript text", draft.transcriptText)
        assertEquals("en", draft.transcriptLanguageCode)
        assertEquals(true, draft.transcriptIsGenerated)
        assertEquals(instant, draft.createdAt)
        assertTrue(draft.id.isNotEmpty())
        // Only the transcript/title abstractions exist in this coordinator; no analysis dependency.
        assertEquals(1, fixture.transcript.calls)
    }

    @Test fun sharedTitleWinsAndSkipsMetadataRequest() = runTest {
        val fixture = Fixture()
        val titled = input.copy(sharedTitle = "  Shared title  ")
        fixture.coordinator.ingest(titled)
        assertEquals("Shared title", fixture.repository.lastDraft?.title)
        assertEquals("Shared title", fixture.transcript.lastTitle)
        assertEquals(0, fixture.title.calls)
    }

    @Test fun missingOrFailedMetadataFallsBackToCanonicalUrl() = runTest {
        val fixture = Fixture()
        fixture.title.value = "  "
        fixture.coordinator.ingest(input)
        assertEquals(input.identity.canonicalUrl.toString(), fixture.repository.lastDraft?.title)
        fixture.title.failure = IllegalStateException("metadata failed")
        fixture.coordinator.ingest(input)
        assertEquals(input.identity.canonicalUrl.toString(), fixture.repository.lastDraft?.title)
    }

    @Test fun identityMismatchAndInvalidInputNeverSave() = runTest {
        val fixture = Fixture()
        fixture.transcript.response = transcript().copy(videoId = "aaaaaaaaaaa")
        assertSame(ShareIngestionFailure.IdentityMismatch, failure { fixture.coordinator.ingest(input) })
        assertEquals(0, fixture.repository.saves)
        val invalid = input.copy(identity = input.identity.copy(sourceKey = "youtube:other"))
        assertSame(ShareIngestionFailure.InvalidIdentity, failure { fixture.coordinator.ingest(invalid) })
        assertEquals(1, fixture.transcript.calls)
    }

    @Test fun transcriptErrorsDoNotSaveAndHaveTypedFailures() = runTest {
        val cases = listOf(
            "INVALID_YOUTUBE_URL" to ShareIngestionFailure.InvalidIdentity,
            "TRANSCRIPT_UNAVAILABLE" to ShareIngestionFailure.TranscriptUnavailable,
            "EMPTY_TRANSCRIPT" to ShareIngestionFailure.TranscriptUnavailable,
            "TRANSCRIPT_FETCH_FAILED" to ShareIngestionFailure.Provider,
        )
        for ((code, expected) in cases) {
            val fixture = Fixture()
            fixture.transcript.failure = ApiError.Backend(502, code, "backend detail")
            assertSame(expected, failure { fixture.coordinator.ingest(input) })
            assertEquals(0, fixture.repository.saves)
        }
    }

    @Test fun storageFailureIsTypedAndDoesNotStartNetwork() = runTest {
        val fixture = Fixture()
        fixture.repository.prepareFailure = IllegalStateException("database closed")
        assertSame(ShareIngestionFailure.Storage, failure { fixture.coordinator.ingest(input) })
        assertEquals(0, fixture.transcript.calls)
    }

    @Test fun concurrentTrashChangeReturnsOriginalRestoreTarget() = runTest {
        val fixture = Fixture()
        fixture.repository.saveOutcome = SaveNoteOutcome.RestoreRequired(note(trashed = true))
        assertEquals(ShareIngestionResult.RestoreRequired("existing"), fixture.coordinator.ingest(input))
        assertEquals(1, fixture.repository.saves)
    }

    @Test fun concurrentActiveChangeReturnsExistingNote() = runTest {
        val fixture = Fixture()
        fixture.repository.saveOutcome = SaveNoteOutcome.AlreadySaved(note())
        assertEquals(ShareIngestionResult.AlreadySaved("existing"), fixture.coordinator.ingest(input))
    }

    @Test fun cancellationBeforeDraftLeavesNoNote() = runTest {
        val fixture = Fixture()
        val gate = CompletableDeferred<Unit>()
        fixture.transcript.beforeReturn = { gate.await() }
        val work = async(StandardTestDispatcher(testScheduler)) { fixture.coordinator.ingest(input) }
        testScheduler.runCurrent()
        work.cancel()
        gate.complete(Unit)
        advanceUntilIdle()
        assertFalse(work.isCompleted && fixture.repository.saves > 0)
        assertEquals(0, fixture.repository.saves)
    }

    @Test fun restoreKeepsOriginalNoteAndMissingDoesNotCreateReplacement() = runTest {
        val fixture = Fixture()
        fixture.repository.restoreOutcome = RestoreOutcome.Restored(note())
        assertEquals(ShareIngestionResult.AlreadySaved("existing"), fixture.coordinator.restore("existing"))
        fixture.repository.restoreOutcome = RestoreOutcome.AlreadyActive(note())
        assertEquals(ShareIngestionResult.AlreadySaved("existing"), fixture.coordinator.restore("existing"))
        fixture.repository.restoreOutcome = RestoreOutcome.Missing
        assertSame(ShareIngestionFailure.Storage, failure { fixture.coordinator.restore("existing") })
        assertEquals(0, fixture.repository.saves)
        assertEquals(0, fixture.transcript.calls)
        assertEquals(3, fixture.repository.restores)
    }

    private suspend fun failure(block: suspend () -> Unit): ShareIngestionFailure = try {
        block()
        error("Expected ShareIngestionFailure")
    } catch (error: ShareIngestionFailure) {
        error
    }

    private fun note(trashed: Boolean = false) = ContentNote(
        "existing", input.identity.sourceKey, "youtube", input.identity.videoId,
        input.sourceUrl, input.identity.canonicalUrl.toString(), "Existing", "transcript-1",
        "Transcript text", "en", true, instant, if (trashed) instant else null,
    )

    private fun transcript() = YoutubeTranscriptResponse(
        "transcript-1", input.identity.videoId, input.identity.canonicalUrl.toString(),
        "Transcript text", "en", "English", true,
    )

    private inner class Fixture {
        val repository = FakeRepository()
        val transcript = FakeTranscript()
        val title = FakeTitle()
        val coordinator = ShareIngestionCoordinator(repository, transcript, title) { instant }
    }

    private inner class FakeRepository : ContentNoteRepository {
        var preparation: ShareNotePreparation = ShareNotePreparation.Absent
        var saveOutcome: SaveNoteOutcome? = null
        var restoreOutcome: RestoreOutcome = RestoreOutcome.Missing
        var prepareFailure: Exception? = null
        var saves = 0
        var restores = 0
        var lastDraft: ContentNoteDraft? = null

        override fun observeActive() = kotlinx.coroutines.flow.emptyFlow<List<ContentNote>>()
        override fun observeTrash() = kotlinx.coroutines.flow.emptyFlow<List<ContentNote>>()
        override suspend fun find(id: String): ContentNote? = null
        override suspend fun prepareForShare(sourceKey: String): ShareNotePreparation {
            prepareFailure?.let { throw it }
            return preparation
        }
        override suspend fun saveOrReuse(draft: ContentNoteDraft): SaveNoteOutcome {
            saves++
            lastDraft = draft
            return saveOutcome ?: SaveNoteOutcome.Saved(note().copy(id = "new"))
        }
        override suspend fun moveToTrash(id: String, at: Instant) = false
        override suspend fun restore(id: String): RestoreOutcome {
            restores++
            return restoreOutcome
        }
        override suspend fun deletePermanently(id: String) = false
        override suspend fun purgeExpired(cutoff: Instant) = 0
    }

    private inner class FakeTranscript : YoutubeTranscriptFetching {
        var calls = 0
        var lastTitle: String? = null
        var response = transcript()
        var failure: Exception? = null
        var beforeReturn: suspend () -> Unit = {}
        override suspend fun fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse {
            calls++
            lastTitle = title
            beforeReturn()
            failure?.let { throw it }
            return response
        }
    }

    private inner class FakeTitle : ShareTitleResolving {
        var calls = 0
        var value: String? = null
        var failure: Exception? = null
        var beforeReturn: suspend () -> Unit = {}
        override suspend fun resolve(canonicalUrl: HttpUrl): String? {
            calls++
            beforeReturn()
            failure?.let { throw it }
            return value
        }
    }
}
