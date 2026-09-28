package com.andrewkim.reforge.notes

import android.content.Intent
import androidx.room.Room
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.espresso.Espresso
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.andrewkim.reforge.AppContainer
import com.andrewkim.reforge.MainActivity
import com.andrewkim.reforge.ReforgeApplication
import com.andrewkim.reforge.navigation.AnalysisInputSnapshot
import com.andrewkim.reforge.navigation.AppDestination
import com.andrewkim.reforge.sharing.ShareIngesting
import com.andrewkim.reforge.sharing.ShareIngestionResult
import com.andrewkim.reforge.sharing.SharedTextResult
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class NotesScreensTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val app get() = InstrumentationRegistry.getInstrumentation()
        .targetContext.applicationContext as ReforgeApplication
    private lateinit var database: ReforgeDatabase
    private lateinit var repository: RoomContentNoteRepository

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(app, ReforgeDatabase::class.java).build()
        repository = RoomContentNoteRepository(database)
        app.container = AppContainer(app, repository)
    }

    @After fun tearDown() {
        app.container = AppContainer(app)
        database.close()
    }

    @Test fun emptyStatesAndTrashNavigation() {
        ActivityScenario.launch<MainActivity>(launcher()).use {
            compose.onNodeWithText("My Notes").performClick()
            waitFor("my-notes")
            compose.onNodeWithText("No saved notes yet.").assertExists()
            compose.onNodeWithText("Trash").performClick()
            waitFor("trash")
            compose.onNodeWithText("Trash is empty.").assertExists()
            Espresso.pressBack()
            waitFor("my-notes")
        }
    }

    @Test fun activeOrderAndMoveConfirmation() {
        val older = save("dQw4w9WgXcQ", "Older", Instant.parse("2026-09-01T00:00:00Z"))
        val newer = save("a1B2c3D4e5F", "Newer", Instant.parse("2026-09-02T00:00:00Z"))
        ActivityScenario.launch<MainActivity>(launcher()).use {
            compose.onNodeWithText("My Notes").performClick()
            waitFor("note-row-${newer.id}")
            assertTrue(rowTop("note-row-${newer.id}") < rowTop("note-row-${older.id}"))
            compose.onAllNodesWithText("Move to Trash")[0].performClick()
            compose.onNodeWithText("Move this note to Trash? You can restore it for 30 days.").assertExists()
            compose.onNodeWithText("Cancel").performClick()
            assertEquals(2, runBlocking { repository.observeActive().first().size })
            compose.onAllNodesWithText("Move to Trash")[0].performClick()
            compose.onNodeWithTag("confirm-move").performClick()
            compose.waitUntil(5_000) { runBlocking { repository.observeTrash().first().size } == 1 }
            assertEquals(newer.id, runBlocking { repository.observeTrash().first().single().id })
        }
    }

    @Test fun detailFieldsAndAnalysisSnapshotSurviveConcurrentDelete() {
        val note = save("dQw4w9WgXcQ", "Displayed title", Instant.now())
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            compose.onNodeWithText("My Notes").performClick()
            compose.onNodeWithText("Displayed title").performClick()
            waitFor("note-detail")
            compose.onNodeWithTag("note-thumbnail").assertExists()
            compose.onNodeWithText("Open in YouTube").assertExists()
            compose.onNodeWithText("Language: en").assertExists()
            compose.onNodeWithText("Not generated").assertExists()
            compose.onNodeWithTag("note-transcript").assertExists()
            compose.onNodeWithText("Analyze").performClick()
            scenario.onActivity {
                assertEquals(AnalysisInputSnapshot(note.title, note.canonicalUrl), it.appCoordinator.analysisInput.value)
                assertEquals(AppDestination.HOME, it.appCoordinator.currentRoute())
            }
            runBlocking { repository.deletePermanently(note.id) }
            scenario.onActivity {
                assertEquals(AnalysisInputSnapshot(note.title, note.canonicalUrl), it.appCoordinator.analysisInput.value)
            }
        }
    }

    @Test fun missingOrTrashedDetailReturnsToActiveList() {
        val note = save("dQw4w9WgXcQ", "To remove", Instant.now())
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            scenario.onActivity { it.appCoordinator.openNote(note.id) }
            waitFor("detail-title")
            runBlocking { repository.moveToTrash(note.id, Instant.now()) }
            waitFor("my-notes")
            scenario.onActivity { assertEquals(AppDestination.NOTES, it.appCoordinator.currentRoute()) }
            scenario.onActivity { it.appCoordinator.openNote("missing-id") }
            waitFor("my-notes")
            scenario.onActivity { assertEquals(AppDestination.NOTES, it.appCoordinator.currentRoute()) }
        }
    }

    @Test fun trashOrderingRestoreAndPermanentDeleteConfirmation() {
        val older = save("dQw4w9WgXcQ", "Older trash", Instant.now())
        val newer = save("a1B2c3D4e5F", "Newer trash", Instant.now())
        runBlocking {
            repository.moveToTrash(older.id, Instant.now().minus(2, ChronoUnit.DAYS))
            repository.moveToTrash(newer.id, Instant.now().minus(1, ChronoUnit.DAYS))
        }
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            compose.onNodeWithText("My Notes").performClick()
            compose.onNodeWithText("Trash").performClick()
            waitFor("trash-row-${newer.id}")
            assertTrue(rowTop("trash-row-${newer.id}") < rowTop("trash-row-${older.id}"))
            compose.onAllNodesWithText("Restore")[0].performClick()
            compose.waitUntil(5_000) { runBlocking { repository.observeTrash().first().size } == 1 }
            scenario.onActivity { assertEquals(AppDestination.TRASH, it.appCoordinator.currentRoute()) }
            compose.onNodeWithText("Delete").performClick()
            compose.onNodeWithText("Delete this note permanently? This can’t be undone.").assertExists()
            compose.onNodeWithText("Cancel").performClick()
            assertEquals(1, runBlocking { repository.observeTrash().first().size })
            compose.onNodeWithText("Delete").performClick()
            compose.onNodeWithTag("confirm-delete").performClick()
            compose.onNodeWithText("Trash is empty.").assertExists()
        }
    }

    @Test fun trashPurgeFailureRetriesOnNextResume() {
        val expired = save("dQw4w9WgXcQ", "Expired", Instant.now())
        runBlocking { repository.moveToTrash(expired.id, Instant.now().minus(31, ChronoUnit.DAYS)) }
        val calls = AtomicInteger()
        val failingOnce = object : ContentNoteRepository by repository {
            override suspend fun purgeExpired(cutoff: Instant): Int {
                if (calls.incrementAndGet() == 1) throw IllegalStateException("temporary")
                return repository.purgeExpired(cutoff)
            }
        }
        app.container = AppContainer(app, failingOnce)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            compose.onNodeWithText("My Notes").performClick()
            compose.onNodeWithText("Trash").performClick()
            waitFor("trash-row-${expired.id}")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.NOTES_GRAPH) }
            compose.waitUntil(5_000) { calls.get() >= 2 }
            compose.onNodeWithText("Trash is empty.").assertExists()
        }
    }

    @Test fun detailAndTrashStacksSurviveTabSwitches() {
        val note = save("dQw4w9WgXcQ", "Stack note", Instant.now())
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            scenario.onActivity { it.appCoordinator.openNote(note.id) }
            waitFor("detail-title")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.NOTES_GRAPH) }
            waitFor("detail-title")
            scenario.onActivity {
                assertEquals(AppDestination.NOTE_PATTERN, it.appCoordinator.currentRoute())
            }
            Espresso.pressBack()
            waitFor("my-notes")
            compose.onNodeWithText("Trash").performClick()
            waitFor("trash")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.HOME_GRAPH) }
            waitFor("home")
            scenario.onActivity { it.appCoordinator.selectTab(AppDestination.NOTES_GRAPH) }
            waitFor("trash")
        }
    }

    @Test fun shareSuccessSelectsMyNotesDetail() {
        val note = save("dQw4w9WgXcQ", "Shared", Instant.now())
        app.container = AppContainer(app, repository, object : ShareIngesting {
            override suspend fun ingest(input: SharedTextResult.Valid) = ShareIngestionResult.AlreadySaved(note.id)
            override suspend fun restore(noteId: String) = ShareIngestionResult.AlreadySaved(noteId)
        })
        val activity = InstrumentationRegistry.getInstrumentation().startActivitySync(
            Intent(app, MainActivity::class.java).apply {
                action = Intent.ACTION_SEND
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, note.canonicalUrl)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
            },
        ) as MainActivity
        try {
            waitFor("detail-title")
            InstrumentationRegistry.getInstrumentation().runOnMainSync {
                assertEquals(AppDestination.NOTE_PATTERN, activity.appCoordinator.currentRoute())
                assertEquals(note.id, activity.appCoordinator.currentNoteId())
                assertEquals(null, activity.appCoordinator.analysisInput.value)
            }
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { activity.finish() }
        }
    }

    private fun rowTop(tag: String) = compose.onNodeWithTag(tag).fetchSemanticsNode().boundsInRoot.top
    private fun waitFor(tag: String) {
        compose.waitUntil(10_000) { compose.onAllNodesWithTag(tag).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun launcher() = Intent(app, MainActivity::class.java).apply { action = Intent.ACTION_MAIN }
    private fun save(videoId: String, title: String, at: Instant): ContentNote = runBlocking {
        (repository.saveOrReuse(ContentNoteDraft(
            sourceKey = "youtube:$videoId", sourceType = "youtube", videoId = videoId,
            sourceUrl = "https://youtu.be/$videoId",
            canonicalUrl = "https://www.youtube.com/watch?v=$videoId",
            title = title, transcriptId = "transcript-$videoId", transcriptText = "Full transcript $title",
            transcriptLanguageCode = "en", transcriptIsGenerated = false, createdAt = at,
        )) as SaveNoteOutcome.Saved).note
    }
}
