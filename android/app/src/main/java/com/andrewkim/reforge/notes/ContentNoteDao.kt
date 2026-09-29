package com.andrewkim.reforge.notes

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow
import java.time.Instant

@Dao
interface ContentNoteDao {
    @Query("SELECT * FROM content_notes WHERE trashedAt IS NULL ORDER BY createdAt DESC, id DESC")
    fun observeActive(): Flow<List<ContentNoteEntity>>

    @Query("SELECT * FROM content_notes WHERE trashedAt IS NOT NULL ORDER BY trashedAt DESC, id DESC")
    fun observeTrash(): Flow<List<ContentNoteEntity>>

    @Query("SELECT * FROM content_notes WHERE id = :id LIMIT 1")
    suspend fun find(id: String): ContentNoteEntity?

    @Query("SELECT * FROM content_notes WHERE sourceKey = :sourceKey LIMIT 1")
    suspend fun findBySourceKey(sourceKey: String): ContentNoteEntity?

    @Insert
    suspend fun insert(note: ContentNoteEntity)

    @Query("UPDATE content_notes SET trashedAt = :at WHERE id = :id AND trashedAt IS NULL")
    suspend fun moveToTrash(id: String, at: Instant): Int

    @Query("UPDATE content_notes SET trashedAt = NULL WHERE id = :id AND trashedAt IS NOT NULL")
    suspend fun restore(id: String): Int

    @Query("DELETE FROM content_notes WHERE id = :id")
    suspend fun deletePermanently(id: String): Int

    @Query("DELETE FROM content_notes WHERE trashedAt IS NOT NULL AND trashedAt <= :cutoff")
    suspend fun purgeExpired(cutoff: Instant): Int
}
