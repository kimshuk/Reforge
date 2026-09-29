package com.andrewkim.reforge.navigation

import android.content.Intent
import android.os.Bundle
import android.os.Parcel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModelProvider
import androidx.room.Room
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.andrewkim.reforge.AppContainer
import com.andrewkim.reforge.MainActivity
import com.andrewkim.reforge.ReforgeApplication
import com.andrewkim.reforge.network.ShareTitleResolving
import com.andrewkim.reforge.network.YoutubeTranscriptFetching
import com.andrewkim.reforge.network.YoutubeTranscriptResponse
import com.andrewkim.reforge.notes.ContentNoteDraft
import com.andrewkim.reforge.notes.ReforgeDatabase
import com.andrewkim.reforge.notes.RoomContentNoteRepository
import com.andrewkim.reforge.sharing.ShareIngestionCoordinator
import com.andrewkim.reforge.sharing.ShareImportState
import com.andrewkim.reforge.sharing.ShareImportViewModel
import com.andrewkim.reforge.sharing.ShareIntentParser
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareNavigationTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val app get() = InstrumentationRegistry.getInstrumentation()
        .targetContext.applicationContext as ReforgeApplication
    private lateinit var database: ReforgeDatabase
    private lateinit var repository: RoomContentNoteRepository
    private lateinit var transcript: ControlledTranscript

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(app, ReforgeDatabase::class.java).build()
        repository = RoomContentNoteRepository(database)
        transcript = ControlledTranscript()
        app.container = AppContainer(
            app,
            repository,
            ShareIngestionCoordinator(repository, transcript, object : ShareTitleResolving {
                override suspend fun resolve(canonicalUrl: HttpUrl): String? = null
            }),
        )
    }

    @After fun tearDown() {
        app.container = AppContainer(app)
        database.close()
    }

    @Test fun coldShareStoresOneNoteAndNeutralizesLaunchIntent() {
        val activity = coldShare(FIRST)
        try {
            waitFor("note-detail")
            assertEquals(1, activeCount())
            assertEquals(Intent.ACTION_MAIN, activity.intent.action)
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { activity.finish() }
        }
    }

    @Test fun invalidAndAmbiguousActionSendShowExactErrorAndBackFinishesColdTask() {
        for (text in listOf("invalid", "$FIRST $SECOND")) {
            val activity = coldShare(text)
            try {
                compose.onNodeWithText("Please enter a valid YouTube URL.").assertExists()
                compose.onNodeWithText("Back").performClick()
                compose.waitUntil(5_000) { activity.isFinishing }
                assertEquals(0, activeCount())
            } finally {
                InstrumentationRegistry.getInstrumentation().runOnMainSync { activity.finish() }
            }
        }
    }

    @Test fun secondExternalIntentUsesSingleTaskAndCancelsOldGeneration() {
        val firstGate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            val initialActivity = arrayOfNulls<MainActivity>(1)
            scenario.onActivity { initialActivity[0] = it }
            sendToExisting(SECOND)
            waitFor("note-detail")
            scenario.onActivity { assertTrue(initialActivity[0] === it) }
            firstGate.complete(response(FIRST_ID))
            compose.waitForIdle()
            assertEquals(1, activeCount())
            assertEquals(SECOND_ID, runBlocking { repository.observeActive().first().single().videoId })
        }
    }

    @Test fun rotationDuringLoadingKeepsOneImportAndOneInsert() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            scenario.recreate()
            waitFor("share-loading")
            gate.complete(response(FIRST_ID))
            waitFor("note-detail")
            assertEquals(1, transcript.calls.get())
            assertEquals(1, activeCount())
        }
    }

    @Test fun completionWhileCollectorStoppedRecoversAfterLifecycleRestart() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED)
            gate.complete(response(FIRST_ID))
            compose.waitUntil(5_000) { activeCount() == 1 }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED)
            waitFor("note-detail")
            assertEquals(1, activeCount())
        }
    }

    @Test fun olderQueuedCompletionCannotNavigateAfterNewGeneration() {
        val firstGate = transcript.block(FIRST_ID)
        val secondGate = transcript.block(SECOND_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            val activity = arrayOfNulls<MainActivity>(1)
            scenario.onActivity { activity[0] = it }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED)
            firstGate.complete(response(FIRST_ID))
            compose.waitUntil(5_000) { activeCount() == 1 }
            InstrumentationRegistry.getInstrumentation().runOnMainSync {
                activity[0]!!.appCoordinator.acceptShare(share(SECOND))
            }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED)
            waitFor("share-loading")
            secondGate.complete(response(SECOND_ID))
            waitFor("note-detail")
            assertEquals(2, activeCount())
            scenario.onActivity {
                assertEquals(SECOND_ID, runBlocking { repository.find(
                    it.appCoordinator.currentNoteId() ?: error("No note detail"),
                ) }?.videoId)
            }
        }
    }

    @Test fun savedStateHandleRoundTripsThroughParcelBeforeAndAfterAcknowledgement() {
        val note = save(FIRST_ID)
        val handle = SavedStateHandle()
        val viewModel = ShareImportViewModel(app.container.ingestor, handle)
        viewModel.accept(ShareIntentParser.parse(share(FIRST)))
        compose.waitUntil(5_000) { viewModel.state.value is ShareImportState.Completed }
        val completed = viewModel.state.value as ShareImportState.Completed
        assertEquals(note.id, completed.noteId)
        val restored = ShareImportViewModel(app.container.ingestor, parcelRoundTrip(handle))
        assertEquals(completed, restored.state.value)
        viewModel.acknowledgeDetailOpened(completed.generation, completed.noteId)
        val acknowledged = ShareImportViewModel(app.container.ingestor, parcelRoundTrip(handle))
        assertEquals(true, (acknowledged.state.value as ShareImportState.Completed).navigationAcknowledged)
        assertEquals(1, activeCount())
        assertEquals(0, transcript.calls.get())
    }

    @Test fun bundleCapturedBeforeCommitRecoversCompletedNoteInFreshViewModel() {
        val gate = transcript.block(FIRST_ID)
        val handle = SavedStateHandle()
        val first = ShareImportViewModel(app.container.ingestor, handle)
        first.accept(ShareIntentParser.parse(share(FIRST)))
        compose.waitUntil(5_000) { transcript.calls.get() == 1 }
        assertTrue(first.state.value is ShareImportState.Loading)
        val stoppedSnapshot = parcelRoundTrip(handle)

        gate.complete(response(FIRST_ID))
        compose.waitUntil(5_000) { first.state.value is ShareImportState.Completed }
        val committed = runBlocking { repository.observeActive().first().single() }
        val fresh = ShareImportViewModel(app.container.ingestor, stoppedSnapshot)
        compose.waitUntil(5_000) { fresh.state.value is ShareImportState.Completed }

        assertEquals(ShareImportState.Completed(1, committed.id), fresh.state.value)
        assertEquals(1, activeCount())
        assertEquals(1, transcript.calls.get())
    }

    @Test fun activityRestoresPreCommitBundleWithFreshViewModelAndOpensCommittedDetailOnce() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            lateinit var stoppedActivity: MainActivity
            lateinit var oldViewModel: ShareImportViewModel
            lateinit var preCommitHandles: Bundle
            scenario.onActivity { activity ->
                stoppedActivity = activity
                oldViewModel = ViewModelProvider(activity)[ShareImportViewModel::class.java]
                // Save exactly the provider Bundle that Android captures before stopping.
                preCommitHandles = parcelRoundTrip(requireNotNull(
                    activity.savedStateRegistry.getSavedStateProvider(SAVED_STATE_HANDLES_KEY),
                ).saveState())
                assertTrue(oldViewModel.state.value is ShareImportState.Loading)
            }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED)
            gate.complete(response(FIRST_ID))
            compose.waitUntil(5_000) { oldViewModel.state.value is ShareImportState.Completed }
            val note = runBlocking { repository.observeActive().first().single() }

            InstrumentationRegistry.getInstrumentation().runOnMainSync {
                stoppedActivity.viewModelStore.clear()
                // ActivityScenario normally captures a NEW Bundle on recreate. Freeze only
                // the VM provider at the earlier OS snapshot to model process death after stop.
                stoppedActivity.savedStateRegistry.unregisterSavedStateProvider(SAVED_STATE_HANDLES_KEY)
                stoppedActivity.savedStateRegistry.registerSavedStateProvider(SAVED_STATE_HANDLES_KEY) {
                    preCommitHandles
                }
            }
            scenario.recreate()
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED)
            waitFor("note-detail")
            scenario.onActivity { activity ->
                assertNotSame(oldViewModel, ViewModelProvider(activity)[ShareImportViewModel::class.java])
                assertEquals(note.id, activity.appCoordinator.currentNoteId())
            }
            scenario.recreate()
            waitFor("note-detail")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            compose.onNodeWithTag("share-import").assertDoesNotExist()
            assertEquals(1, activeCount())
            assertEquals(1, transcript.calls.get())
        }
    }

    @Test fun backFromWarmShareReturnsToOriginDetail() {
        val note = save(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            scenario.onActivity { it.appCoordinator.openNote(note.id) }
            waitFor("note-detail")
            sendToExisting("invalid")
            compose.onNodeWithText("Please enter a valid YouTube URL.").assertExists()
            compose.onNodeWithText("Back").performClick()
            scenario.onActivity { assertEquals(AppDestination.NOTE_PATTERN, it.appCoordinator.currentRoute()) }
            waitFor("note-detail")
            assertEquals(1, activeCount())
        }
    }

    @Test fun generalLaunchWhileImportingReturnsHomeWithoutRestoringShare() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            app.startActivity(launcher().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            waitFor("home")
            gate.complete(response(FIRST_ID))
            compose.waitForIdle()
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.NOTES_GRAPH) }
            waitFor("my-notes")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            assertEquals(0, activeCount())
        }
    }

    @Test fun generalLaunchDiscardsQueuedCompletionWithoutDeletingSavedNote() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            val activity = arrayOfNulls<MainActivity>(1)
            scenario.onActivity { activity[0] = it }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED)
            gate.complete(response(FIRST_ID))
            compose.waitUntil(5_000) { activeCount() == 1 }
            InstrumentationRegistry.getInstrumentation().runOnMainSync {
                activity[0]!!.appCoordinator.acceptShare(launcher())
            }
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED)
            waitFor("home")
            compose.onNodeWithTag("note-detail").assertDoesNotExist()
            scenario.recreate()
            waitFor("home")
            compose.onNodeWithTag("note-detail").assertDoesNotExist()
            assertEquals(1, activeCount())
            assertEquals(1, transcript.calls.get())
        }
    }

    @Test fun processRecreationDuringLoadingExitsShareWithoutReplay() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            scenario.onActivity { it.viewModelStore.clear() }
            scenario.recreate()
            waitFor("home")
            compose.onNodeWithTag("share-import").assertDoesNotExist()
            gate.complete(response(FIRST_ID))
            compose.waitForIdle()
            assertEquals(1, transcript.calls.get())
            assertEquals(0, activeCount())
        }
    }

    @Test fun processRecreationFromErrorExitsBlankShareRoute() {
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting("invalid")
            compose.onNodeWithText("Please enter a valid YouTube URL.").assertExists()
            scenario.onActivity { it.viewModelStore.clear() }
            scenario.recreate()
            waitFor("home")
            compose.onNodeWithTag("share-import").assertDoesNotExist()
            assertEquals(0, activeCount())
        }
    }

    @Test fun processRecreationFromRestorePromptExitsWithoutChangingTrash() {
        val note = save(FIRST_ID)
        runBlocking { repository.moveToTrash(note.id, Instant.now()) }
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            compose.onNodeWithText("This video is in Trash. Restore it?").assertExists()
            scenario.onActivity { it.viewModelStore.clear() }
            scenario.recreate()
            waitFor("home")
            compose.onNodeWithTag("share-import").assertDoesNotExist()
            assertEquals(note.id, runBlocking { repository.observeTrash().first().single().id })
            assertEquals(0, transcript.calls.get())
        }
    }

    @Test fun restoredCompletedStateNavigatesOnceAfterActivitySavedStateRecreation() {
        val gate = transcript.block(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("share-loading")
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.CREATED)
            gate.complete(response(FIRST_ID))
            compose.waitUntil(5_000) { activeCount() == 1 }
            scenario.recreate()
            scenario.moveToState(androidx.lifecycle.Lifecycle.State.RESUMED)
            waitFor("note-detail")
            scenario.recreate()
            waitFor("note-detail")
            assertEquals(1, activeCount())
            assertEquals(1, transcript.calls.get())
        }
    }

    @Test fun acknowledgedRecreationDoesNotReopenDetail() {
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            sendToExisting(FIRST)
            waitFor("note-detail")
            scenario.recreate() // Real Activity SavedStateRegistry save/restore path.
            waitFor("note-detail")
            scenario.onActivity {
                assertEquals(AppDestination.NOTE_PATTERN, it.appCoordinator.currentRoute())
                it.appCoordinator.selectTab(AppDestination.HOME_GRAPH)
                assertEquals(AppDestination.HOME, it.appCoordinator.currentRoute())
            }
            waitFor("home")
            compose.onNodeWithTag("note-detail").assertDoesNotExist()
            assertEquals(1, activeCount())
        }
    }

    @Test fun tabsRestoreIndependentDetailStack() {
        val note = save(FIRST_ID)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            scenario.onActivity { it.appCoordinator.openNote(note.id) }
            waitFor("note-detail")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.NOTES_GRAPH) }
            waitFor("note-detail")
        }
    }

    @Test fun trashCancelLeavesOriginalUntouchedAndRestoreOpensSameNote() {
        val note = save(FIRST_ID)
        runBlocking { repository.moveToTrash(note.id, Instant.now()) }
        val firstActivity = coldShare(FIRST)
        try {
            compose.onNodeWithText("This video is in Trash. Restore it?").assertExists()
            compose.onNodeWithText("Cancel").performClick()
            compose.waitUntil(5_000) { firstActivity.isFinishing }
            assertEquals(0, activeCount())
            assertEquals(1, runBlocking { repository.observeTrash().first().size })
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { firstActivity.finish() }
        }
        val secondActivity = coldShare(FIRST)
        try {
            compose.onNodeWithText("Restore").performClick()
            waitFor("note-detail")
            assertEquals(note.id, runBlocking { repository.observeActive().first().single().id })
            assertEquals(0, transcript.calls.get())
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { secondActivity.finish() }
        }
    }

    private fun waitFor(tag: String) {
        compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    }

    private fun activeCount(): Int = runBlocking { repository.observeActive().first().size }

    private fun parcelRoundTrip(handle: SavedStateHandle): SavedStateHandle =
        SavedStateHandle.createHandle(parcelRoundTrip(handle.savedStateProvider().saveState()), null)

    private fun parcelRoundTrip(bundle: Bundle): Bundle {
        val parcel = Parcel.obtain()
        return try {
            bundle.writeToParcel(parcel, 0)
            parcel.setDataPosition(0)
            Bundle.CREATOR.createFromParcel(parcel)
        } finally {
            parcel.recycle()
        }
    }

    private fun save(videoId: String) = runBlocking {
        val draft = ContentNoteDraft(
            sourceKey = "youtube:$videoId", sourceType = "youtube", videoId = videoId,
            sourceUrl = "https://youtu.be/$videoId",
            canonicalUrl = "https://www.youtube.com/watch?v=$videoId",
            title = "Title", transcriptId = "transcript-$videoId", transcriptText = "Text",
            transcriptLanguageCode = "en", transcriptIsGenerated = false, createdAt = Instant.now(),
        )
        repository.saveOrReuse(draft).let { (it as com.andrewkim.reforge.notes.SaveNoteOutcome.Saved).note }
    }

    private fun launcher() = Intent(app, MainActivity::class.java).apply { action = Intent.ACTION_MAIN }
    private fun coldShare(text: String): MainActivity =
        InstrumentationRegistry.getInstrumentation().startActivitySync(
            share(text).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
        ) as MainActivity

    private fun sendToExisting(text: String) {
        app.startActivity(share(text).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
    private fun share(text: String) = Intent(app, MainActivity::class.java).apply {
        action = Intent.ACTION_SEND
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
    }

    private class ControlledTranscript : YoutubeTranscriptFetching {
        val calls = AtomicInteger()
        private val gates = ConcurrentHashMap<String, CompletableDeferred<YoutubeTranscriptResponse>>()
        fun block(id: String) = CompletableDeferred<YoutubeTranscriptResponse>().also { gates[id] = it }
        override suspend fun fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse {
            calls.incrementAndGet()
            val id = requireNotNull(canonicalUrl.queryParameter("v"))
            return gates[id]?.await() ?: response(id)
        }
    }

    private companion object {
        const val SAVED_STATE_HANDLES_KEY = "androidx.lifecycle.internal.SavedStateHandlesProvider"
        const val FIRST_ID = "dQw4w9WgXcQ"
        const val SECOND_ID = "a1B2c3D4e5F"
        const val FIRST = "https://youtu.be/$FIRST_ID"
        const val SECOND = "https://youtu.be/$SECOND_ID"
        fun response(id: String) = YoutubeTranscriptResponse(
            transcriptId = "transcript-$id", videoId = id,
            canonicalYoutubeUrl = "https://www.youtube.com/watch?v=$id",
            transcriptText = "Text", languageCode = "en", language = "English", isGenerated = false,
        )
    }
}
