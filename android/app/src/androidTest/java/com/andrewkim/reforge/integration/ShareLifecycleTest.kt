package com.andrewkim.reforge.integration

import android.content.Intent
import androidx.compose.ui.test.junit4.createEmptyComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.ProcessLifecycleOwner
import androidx.room.Room
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.andrewkim.reforge.AppContainer
import com.andrewkim.reforge.MainActivity
import com.andrewkim.reforge.ReforgeApplication
import com.andrewkim.reforge.network.ShareTitleResolving
import com.andrewkim.reforge.network.YoutubeTranscriptFetching
import com.andrewkim.reforge.network.YoutubeTranscriptResponse
import com.andrewkim.reforge.notes.ContentNoteDraft
import com.andrewkim.reforge.notes.ContentNoteRepository
import com.andrewkim.reforge.notes.ReforgeDatabase
import com.andrewkim.reforge.notes.RoomContentNoteRepository
import com.andrewkim.reforge.sharing.ShareIngestionCoordinator
import java.time.Duration
import java.time.Instant
import java.util.UUID
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareLifecycleTest {
    @get:Rule val compose = createEmptyComposeRule()
    private val app get() = InstrumentationRegistry.getInstrumentation()
        .targetContext.applicationContext as ReforgeApplication
    private lateinit var database: ReforgeDatabase
    private lateinit var repository: RoomContentNoteRepository
    private var databaseName: String? = null
    private val now = Instant.parse("2026-09-29T00:00:00Z")

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(app, ReforgeDatabase::class.java).build()
        repository = RoomContentNoteRepository(database)
        app.container = AppContainer(app, repository)
    }

    @After fun tearDown() {
        app.container = AppContainer(app)
        database.close()
        databaseName?.let(app::deleteDatabase)
    }

    @Test fun coldShareSurvivesActivityRestartAndWarmShareReusesStoredNote() {
        waitForBackground()
        val name = "share-lifecycle-${UUID.randomUUID()}.db"
        databaseName = name
        database.close()
        database = Room.databaseBuilder(app, ReforgeDatabase::class.java, name).build()
        repository = RoomContentNoteRepository(database)
        val transcriptCalls = AtomicInteger()
        fun container() = AppContainer(
            app, repository,
            ShareIngestionCoordinator(repository, object : YoutubeTranscriptFetching {
                override suspend fun fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse {
                    transcriptCalls.incrementAndGet()
                    return YoutubeTranscriptResponse(
                        transcriptId = "transcript-$VIDEO_ID", videoId = VIDEO_ID,
                        canonicalYoutubeUrl = CANONICAL_URL, transcriptText = "Transcript",
                        languageCode = "en", language = "English", isGenerated = false,
                    )
                }
            }, object : ShareTitleResolving {
                override suspend fun resolve(canonicalUrl: HttpUrl): String? = null
            }),
        )
        app.container = container()
        val activity = InstrumentationRegistry.getInstrumentation().startActivitySync(
            share().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK),
        ) as MainActivity
        try {
            waitFor("note-detail")
            assertEquals(1, runBlocking { repository.observeActive().first().size })
        } finally {
            InstrumentationRegistry.getInstrumentation().runOnMainSync { activity.finish() }
        }
        waitForBackground()
        database.close()
        database = Room.databaseBuilder(app, ReforgeDatabase::class.java, name).build()
        repository = RoomContentNoteRepository(database)
        app.container = container()
        val persistedId = runBlocking { repository.observeActive().first().single().id }
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitFor("home")
            app.startActivity(share().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            waitFor("note-detail")
            scenario.onActivity { assertEquals(persistedId, it.appCoordinator.currentNoteId()) }
            assertEquals(1, runBlocking { repository.observeActive().first().size })
            assertEquals(1, transcriptCalls.get())
        }
    }

    @Test fun firstForegroundAndLaterForegroundPurgeExpiredTrash() {
        waitForBackground()
        val first = saveExpired("firstVideo1")
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitUntil { runBlocking { repository.find(first) } == null }
            val second = saveExpired("otherVideo1")
            scenario.moveToState(Lifecycle.State.CREATED)
            waitUntil { ProcessLifecycleOwner.get().lifecycle.currentState == Lifecycle.State.CREATED }
            scenario.moveToState(Lifecycle.State.RESUMED)
            waitUntil { runBlocking { repository.find(second) } == null }
        }
    }

    @Test fun purgeFailureStaysSilentAndRetriesAtNextForeground() {
        waitForBackground()
        val expired = saveExpired("retryVideo1")
        val calls = AtomicInteger()
        val failingOnce = object : ContentNoteRepository by repository {
            override suspend fun purgeExpired(cutoff: Instant): Int {
                if (calls.incrementAndGet() == 1) error("injected database failure")
                return repository.purgeExpired(cutoff)
            }
        }
        app.container = AppContainer(app, failingOnce)
        ActivityScenario.launch<MainActivity>(launcher()).use { scenario ->
            waitUntil { calls.get() == 1 }
            assertNotNull(runBlocking { repository.find(expired) })
            scenario.moveToState(Lifecycle.State.CREATED)
            waitUntil { ProcessLifecycleOwner.get().lifecycle.currentState == Lifecycle.State.CREATED }
            scenario.moveToState(Lifecycle.State.RESUMED)
            waitUntil { calls.get() >= 2 && runBlocking { repository.find(expired) } == null }
            assertEquals(2, calls.get())
        }
    }

    private fun saveExpired(videoId: String): String = runBlocking {
        val note = repository.saveOrReuse(ContentNoteDraft(
            sourceKey = "youtube:$videoId", sourceType = "youtube", videoId = videoId,
            sourceUrl = "https://youtu.be/$videoId", canonicalUrl = "https://www.youtube.com/watch?v=$videoId",
            title = "Title", transcriptId = "transcript-$videoId", transcriptText = "Transcript",
            transcriptLanguageCode = "en", transcriptIsGenerated = false, createdAt = now,
        )) as com.andrewkim.reforge.notes.SaveNoteOutcome.Saved
        repository.moveToTrash(note.note.id, Instant.now().minus(Duration.ofDays(31)))
        note.note.id
    }

    private fun waitFor(tag: String) = waitUntil {
        compose.onAllNodesWithTag(tag)
            .fetchSemanticsNodes(atLeastOneRootRequired = false)
            .isNotEmpty()
    }

    private fun waitUntil(condition: () -> Boolean) = compose.waitUntil(10_000, condition)

    private fun waitForBackground() = waitUntil {
        !ProcessLifecycleOwner.get().lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)
    }

    private fun launcher() = Intent(app, MainActivity::class.java).apply { action = Intent.ACTION_MAIN }
    private fun share() = Intent(app, MainActivity::class.java).apply {
        action = Intent.ACTION_SEND
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, "https://youtu.be/$VIDEO_ID")
    }

    private companion object {
        const val VIDEO_ID = "dQw4w9WgXcQ"
        const val CANONICAL_URL = "https://www.youtube.com/watch?v=$VIDEO_ID"
    }
}
