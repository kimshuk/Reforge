package com.andrewkim.reforge.notes

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import android.content.Context
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.time.Duration
import java.time.Instant
import java.util.UUID

@RunWith(AndroidJUnit4::class)
class RoomContentNoteRepositoryTest {
    private lateinit var database: ReforgeDatabase
    private lateinit var repository: RoomContentNoteRepository
    private val now = Instant.parse("2026-09-29T00:00:00Z")

    @Before fun setUp() {
        database = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(), ReforgeDatabase::class.java,
        ).build()
        repository = RoomContentNoteRepository(database)
    }

    @After fun tearDown() = database.close()

    private fun draft(
        videoId: String = "video${UUID.randomUUID().toString().take(6)}",
        createdAt: Instant = now,
        sourceUrl: String = "https://youtu.be/initial",
        transcriptText: String = "first transcript",
    ) = ContentNoteDraft(
        sourceKey = "youtube:$videoId",
        sourceType = "youtube",
        videoId = videoId,
        sourceUrl = sourceUrl,
        canonicalUrl = "https://www.youtube.com/watch?v=$videoId",
        title = "Original title",
        transcriptId = "transcript-$videoId",
        transcriptText = transcriptText,
        transcriptLanguageCode = "ko",
        transcriptIsGenerated = false,
        createdAt = createdAt,
    )

    private suspend fun save(draft: ContentNoteDraft): ContentNote =
        (repository.saveOrReuse(draft) as SaveNoteOutcome.Saved).note

    @Test fun fieldsRoundTripAndPreparationStates() = runBlocking {
        val input = draft()
        assertEquals(ShareNotePreparation.Absent, repository.prepareForShare(input.sourceKey))
        val note = save(input)
        assertEquals(input.id, note.id)
        assertEquals(input.sourceKey, note.sourceKey)
        assertEquals(input.sourceType, note.sourceType)
        assertEquals(input.videoId, note.videoId)
        assertEquals(input.sourceUrl, note.sourceUrl)
        assertEquals(input.canonicalUrl, note.canonicalUrl)
        assertEquals(input.title, note.title)
        assertEquals(input.transcriptId, note.transcriptId)
        assertEquals(input.transcriptText, note.transcriptText)
        assertEquals(input.transcriptLanguageCode, note.transcriptLanguageCode)
        assertEquals(input.transcriptIsGenerated, note.transcriptIsGenerated)
        assertEquals(input.createdAt, note.createdAt)
        assertNull(note.trashedAt)
        assertEquals(note, repository.find(note.id))
        assertEquals(ShareNotePreparation.Active(note), repository.prepareForShare(input.sourceKey))
        assertTrue(repository.moveToTrash(note.id, now.plusSeconds(1)))
        assertEquals(
            ShareNotePreparation.Trashed(note.copy(trashedAt = now.plusSeconds(1))),
            repository.prepareForShare(input.sourceKey),
        )
    }

    @Test fun nullableTranscriptMetadataRoundTrips() = runBlocking {
        val input = draft().copy(
            transcriptLanguageCode = null,
            transcriptIsGenerated = null,
        )
        val note = save(input)
        assertNull(repository.find(note.id)?.transcriptLanguageCode)
        assertNull(repository.find(note.id)?.transcriptIsGenerated)
        val generated = save(draft().copy(transcriptIsGenerated = true))
        assertEquals(true, repository.find(generated.id)?.transcriptIsGenerated)
    }

    @Test fun activeAndTrashObserveNewestFirst() = runBlocking {
        val oldest = save(draft(createdAt = now.minusSeconds(30)))
        val middle = save(draft(createdAt = now.minusSeconds(20)))
        val newest = save(draft(createdAt = now.minusSeconds(10)))
        assertEquals(listOf(newest, middle, oldest), repository.observeActive().first())
        assertTrue(repository.moveToTrash(oldest.id, now.minusSeconds(5)))
        assertTrue(repository.moveToTrash(newest.id, now.minusSeconds(1)))
        assertEquals(listOf(middle), repository.observeActive().first())
        assertEquals(
            listOf(newest.id, oldest.id), repository.observeTrash().first().map(ContentNote::id),
        )
    }

    @Test fun existingActiveIsNeverMutatedByAnotherDraft() = runBlocking {
        val first = draft(videoId = "sameVideo01", createdAt = now.minusSeconds(5))
        val note = save(first)
        val second = draft(
            videoId = first.videoId,
            createdAt = now,
            sourceUrl = "https://youtu.be/changed",
            transcriptText = "changed transcript",
        )
        assertEquals(SaveNoteOutcome.AlreadySaved(note), repository.saveOrReuse(second))
        assertEquals(listOf(note), repository.observeActive().first())
    }

    @Test fun trashedDuplicateRequiresRestoreWithoutChanges() = runBlocking {
        val input = draft(videoId = "sameVideo02")
        val original = save(input)
        assertTrue(repository.moveToTrash(original.id, now))
        val trashed = original.copy(trashedAt = now)
        assertEquals(
            SaveNoteOutcome.RestoreRequired(trashed),
            repository.saveOrReuse(draft(videoId = input.videoId, transcriptText = "new")),
        )
        assertEquals(listOf(trashed), repository.observeTrash().first())
        assertTrue(repository.observeActive().first().isEmpty())
    }

    @Test fun restorePreservesEveryOriginalField() = runBlocking {
        val original = save(draft())
        assertTrue(repository.moveToTrash(original.id, now))
        assertEquals(RestoreOutcome.Restored(original), repository.restore(original.id))
        assertEquals(RestoreOutcome.AlreadyActive(original), repository.restore(original.id))
        assertEquals(original, repository.find(original.id))
        assertFalse(repository.moveToTrash("missing", now))
        assertEquals(RestoreOutcome.Missing, repository.restore("missing"))
    }

    @Test fun permanentDeleteAndThirtyDayBoundary() = runBlocking {
        val before = save(draft())
        val exact = save(draft())
        val after = save(draft())
        val active = save(draft())
        val cutoff = now.minus(Duration.ofDays(30))
        repository.moveToTrash(before.id, cutoff.minusMillis(1))
        repository.moveToTrash(exact.id, cutoff)
        repository.moveToTrash(after.id, cutoff.plusMillis(1))
        assertEquals(2, repository.purgeExpired(cutoff))
        assertNull(repository.find(before.id))
        assertNull(repository.find(exact.id))
        assertEquals(after.id, repository.find(after.id)?.id)
        assertEquals(active.id, repository.find(active.id)?.id)
        assertEquals(0, repository.purgeExpired(cutoff))
        assertTrue(repository.deletePermanently(after.id))
        assertFalse(repository.deletePermanently(after.id))
        assertNull(repository.find(after.id))
    }

    @Test fun transactionFailureRollsBackInsertedRow() = runBlocking {
        val input = draft()
        val failing = RoomContentNoteRepository(database, object : RoomContentNoteRepository.SaveObserver {
            override suspend fun afterInsertBeforeCommit(): Unit = error("injected failure")
        })
        val result = runCatching { failing.saveOrReuse(input) }
        assertTrue(result.exceptionOrNull() is IllegalStateException)
        assertNull(repository.find(input.id))
        assertEquals(ShareNotePreparation.Absent, repository.prepareForShare(input.sourceKey))
    }

    @Test fun concurrentSavesConvergeOnOneUnchangedNote() = runBlocking {
        val first = draft(videoId = "sameVideo03", sourceUrl = "first", transcriptText = "first")
        val second = draft(videoId = first.videoId, sourceUrl = "second", transcriptText = "second")
        val one = async(Dispatchers.Default) { repository.saveOrReuse(first) }
        val two = async(Dispatchers.Default) { repository.saveOrReuse(second) }
        val outcomes = listOf(one.await(), two.await())
        val saved = outcomes.filterIsInstance<SaveNoteOutcome.Saved>().single().note
        val reused = outcomes.filterIsInstance<SaveNoteOutcome.AlreadySaved>().single().note
        assertEquals(saved, reused)
        assertEquals(listOf(saved), repository.observeActive().first())
        val winnerDraft = if (saved.id == first.id) first else second
        assertEquals(winnerDraft.sourceUrl, saved.sourceUrl)
        assertEquals(winnerDraft.transcriptText, saved.transcriptText)
        assertEquals(winnerDraft.createdAt, saved.createdAt)
    }

    @Test fun cancellationBeforeSaveLeavesNoRow() = runBlocking {
        val input = draft()
        val gate = CompletableDeferred<Unit>()
        val job = async(Dispatchers.Default, start = CoroutineStart.LAZY) {
            gate.await()
            repository.saveOrReuse(input)
        }
        job.start()
        job.cancel()
        gate.complete(Unit)
        runCatching { job.await() }
        assertEquals(ShareNotePreparation.Absent, repository.prepareForShare(input.sourceKey))
    }

    @Test fun cancellationAfterInsertBeforeCommitRollsBack() = runBlocking {
        val input = draft()
        val inserted = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val hooked = RoomContentNoteRepository(database, object : RoomContentNoteRepository.SaveObserver {
            override suspend fun afterInsertBeforeCommit() {
                inserted.complete(Unit)
                release.await()
            }
        })
        val job = async(Dispatchers.Default) { hooked.saveOrReuse(input) }
        inserted.await()
        job.cancel()
        release.complete(Unit)
        runCatching { job.await() }
        assertEquals(ShareNotePreparation.Absent, repository.prepareForShare(input.sourceKey))
    }

    @Test fun cancellationAfterCommitKeepsCompleteRow() = runBlocking {
        val input = draft()
        val committed = CompletableDeferred<Unit>()
        lateinit var job: kotlinx.coroutines.Deferred<SaveNoteOutcome>
        val hooked = RoomContentNoteRepository(database, object : RoomContentNoteRepository.SaveObserver {
            override fun afterCommit() {
                committed.complete(Unit)
                job.cancel()
            }
        })
        job = async(Dispatchers.Default, start = CoroutineStart.LAZY) { hooked.saveOrReuse(input) }
        job.start()
        committed.await()
        runCatching { job.await() }
        val note = repository.find(input.id)
        assertEquals(input.id, note?.id)
        assertEquals(input.transcriptText, note?.transcriptText)
        assertEquals(input.sourceUrl, note?.sourceUrl)
    }

    @Test fun stateChangedAfterPreflightIsRecheckedForSave() = runBlocking {
        val input = draft()
        val note = save(input)
        assertEquals(ShareNotePreparation.Active(note), repository.prepareForShare(input.sourceKey))
        repository.moveToTrash(note.id, now)
        assertEquals(
            SaveNoteOutcome.RestoreRequired(note.copy(trashedAt = now)),
            repository.saveOrReuse(draft(videoId = input.videoId)),
        )
        assertEquals(1, repository.observeTrash().first().size)
    }

    @Test fun staleRestoreConfirmationCannotRecreateDeletedOrPurgedRow() = runBlocking {
        val note = save(draft())
        repository.moveToTrash(note.id, now.minus(Duration.ofDays(30)))
        assertTrue(repository.prepareForShare(note.sourceKey) is ShareNotePreparation.Trashed)
        assertEquals(1, repository.purgeExpired(now.minus(Duration.ofDays(30))))
        assertEquals(RestoreOutcome.Missing, repository.restore(note.id))

        val another = save(draft())
        repository.moveToTrash(another.id, now)
        assertTrue(repository.prepareForShare(another.sourceKey) is ShareNotePreparation.Trashed)
        assertTrue(repository.deletePermanently(another.id))
        assertEquals(RestoreOutcome.Missing, repository.restore(another.id))
    }

    @Test fun anotherRestoreWinsWithoutOverwritingOriginalFields() = runBlocking {
        val note = save(draft())
        repository.moveToTrash(note.id, now)
        assertTrue(repository.prepareForShare(note.sourceKey) is ShareNotePreparation.Trashed)
        assertEquals(RestoreOutcome.Restored(note), repository.restore(note.id))
        assertEquals(RestoreOutcome.AlreadyActive(note), repository.restore(note.id))
        assertEquals(note, repository.find(note.id))
    }

    @Test fun activeAndTrashedNotesSurviveDatabaseReopen() = runBlocking {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val name = "repository-test-${UUID.randomUUID()}.db"
        var diskDatabase = Room.databaseBuilder(context, ReforgeDatabase::class.java, name).build()
        try {
            var diskRepository = RoomContentNoteRepository(diskDatabase)
            val activeInput = draft()
            val trashedInput = draft()
            val active = (diskRepository.saveOrReuse(activeInput) as SaveNoteOutcome.Saved).note
            val trashed = (diskRepository.saveOrReuse(trashedInput) as SaveNoteOutcome.Saved).note
            diskRepository.moveToTrash(trashed.id, now)
            diskDatabase.close()

            diskDatabase = Room.databaseBuilder(context, ReforgeDatabase::class.java, name).build()
            diskRepository = RoomContentNoteRepository(diskDatabase)
            assertEquals(active, diskRepository.find(active.id))
            assertEquals(trashed.copy(trashedAt = now), diskRepository.find(trashed.id))
            assertEquals(listOf(active), diskRepository.observeActive().first())
            assertEquals(listOf(trashed.id), diskRepository.observeTrash().first().map(ContentNote::id))
        } finally {
            diskDatabase.close()
            context.deleteDatabase(name)
        }
    }
}
