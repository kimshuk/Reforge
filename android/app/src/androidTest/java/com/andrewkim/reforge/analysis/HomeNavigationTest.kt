package com.andrewkim.reforge.analysis

import android.content.Intent
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.room.Room
import androidx.test.core.app.ActivityScenario
import androidx.test.platform.app.InstrumentationRegistry
import com.andrewkim.reforge.AppContainer
import com.andrewkim.reforge.MainActivity
import com.andrewkim.reforge.ReforgeApplication
import com.andrewkim.reforge.network.YouTubeAvailability
import com.andrewkim.reforge.network.YouTubeAvailabilityChecking
import com.andrewkim.reforge.notes.ContentNoteDraft
import com.andrewkim.reforge.notes.ReforgeDatabase
import com.andrewkim.reforge.notes.RoomContentNoteRepository
import com.andrewkim.reforge.notes.SaveNoteOutcome
import java.time.Instant
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Rule
import org.junit.Test

class HomeNavigationTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val app get() = InstrumentationRegistry.getInstrumentation()
        .targetContext.applicationContext as ReforgeApplication
    private lateinit var database: ReforgeDatabase
    private lateinit var repository: RoomContentNoteRepository
    private val calls = AtomicInteger()
    private val received = AtomicReference<AnalyzeRequest>()

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(app, ReforgeDatabase::class.java).build()
        repository = RoomContentNoteRepository(database)
        app.container = AppContainer(app, repository,
            availabilityOverride = YouTubeAvailabilityChecking { YouTubeAvailability.Available("Unused") },
            analysisOverride = AnalysisRunning { request, _ ->
                received.set(request)
                calls.incrementAndGet()
                awaitCancellation()
            })
    }

    @After fun tearDown() {
        app.container = AppContainer(app)
        database.close()
    }

    @Test fun detailSnapshotAnalyzesAfterDeletionAndRotationOnlyOnce() {
        val note = runBlocking {
            (repository.saveOrReuse(ContentNoteDraft(
                sourceKey = "youtube:dQw4w9WgXcQ", sourceType = "youtube", videoId = "dQw4w9WgXcQ",
                sourceUrl = "https://youtu.be/dQw4w9WgXcQ", canonicalUrl = URL,
                title = "Saved title", transcriptId = "transcript", transcriptText = "Text",
                transcriptLanguageCode = "en", transcriptIsGenerated = false, createdAt = Instant.now(),
            )) as SaveNoteOutcome.Saved).note
        }
        val launch = Intent(app, MainActivity::class.java).apply { action = Intent.ACTION_MAIN }
        ActivityScenario.launch<MainActivity>(launch).use { scenario ->
            compose.waitUntil(5_000) { compose.onAllNodesWithTag("home").fetchSemanticsNodes().isNotEmpty() }
            scenario.onActivity { it.appCoordinator.openNote(note.id) }
            compose.onNodeWithTag("detail-title").assertExists()
            compose.onNodeWithText("Analyze").performClick()
            runBlocking { repository.deletePermanently(note.id) }
            compose.waitUntil(5_000) { calls.get() == 1 }
            assertEquals(AnalyzeRequest(title = "Saved title", youtubeUrl = URL), received.get())
            compose.onNodeWithTag("home-progress").assertExists()
            scenario.recreate()
            compose.onNodeWithTag("home-progress").assertExists()
            assertEquals(1, calls.get())
        }
    }

    private companion object { const val URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }
}
