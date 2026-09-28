package com.andrewkim.reforge.notes

import android.database.sqlite.SQLiteConstraintException
import androidx.room.withTransaction
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant

class RoomContentNoteRepository(
    private val database: ReforgeDatabase,
    private val saveObserver: SaveObserver = SaveObserver.None,
) : ContentNoteRepository {
    private val dao = database.contentNoteDao()

    interface SaveObserver {
        suspend fun afterInsertBeforeCommit() {}
        fun afterCommit() {}

        data object None : SaveObserver
    }

    override fun observeActive(): Flow<List<ContentNote>> =
        dao.observeActive().map { rows -> rows.map(ContentNoteEntity::toDomain) }

    override fun observeTrash(): Flow<List<ContentNote>> =
        dao.observeTrash().map { rows -> rows.map(ContentNoteEntity::toDomain) }

    override suspend fun find(id: String): ContentNote? = dao.find(id)?.toDomain()

    override suspend fun prepareForShare(sourceKey: String): ShareNotePreparation =
        dao.findBySourceKey(sourceKey)?.let { row ->
            if (row.trashedAt == null) ShareNotePreparation.Active(row.toDomain())
            else ShareNotePreparation.Trashed(row.toDomain())
        } ?: ShareNotePreparation.Absent

    override suspend fun saveOrReuse(draft: ContentNoteDraft): SaveNoteOutcome {
        currentCoroutineContext().ensureActive()
        val outcome = try {
            database.withTransaction {
                val existing = dao.findBySourceKey(draft.sourceKey)
                if (existing != null) return@withTransaction existing.asSaveOutcome()

                val row = ContentNoteEntity.fromDraft(draft)
                dao.insert(row)
                saveObserver.afterInsertBeforeCommit()
                SaveNoteOutcome.Saved(requireNotNull(dao.find(row.id)).toDomain())
            }
        } catch (error: SQLiteConstraintException) {
            // A different writer may have inserted this source key after the first read.
            dao.findBySourceKey(draft.sourceKey)?.asSaveOutcome() ?: throw error
        }
        saveObserver.afterCommit()
        return outcome
    }

    override suspend fun moveToTrash(id: String, at: Instant): Boolean = database.withTransaction {
        dao.moveToTrash(id, at) > 0
    }

    override suspend fun restore(id: String): RestoreOutcome = database.withTransaction {
        val row = dao.find(id) ?: return@withTransaction RestoreOutcome.Missing
        if (row.trashedAt == null) return@withTransaction RestoreOutcome.AlreadyActive(row.toDomain())
        dao.restore(id)
        RestoreOutcome.Restored(row.copy(trashedAt = null).toDomain())
    }

    override suspend fun deletePermanently(id: String): Boolean = database.withTransaction {
        dao.deletePermanently(id) > 0
    }

    override suspend fun purgeExpired(cutoff: Instant): Int = database.withTransaction {
        dao.purgeExpired(cutoff)
    }

    private fun ContentNoteEntity.asSaveOutcome(): SaveNoteOutcome =
        if (trashedAt == null) SaveNoteOutcome.AlreadySaved(toDomain())
        else SaveNoteOutcome.RestoreRequired(toDomain())
}
