package com.andrewkim.reforge.notes

import kotlinx.coroutines.flow.Flow
import java.time.Instant

interface ContentNoteRepository {
    fun observeActive(): Flow<List<ContentNote>>
    fun observeTrash(): Flow<List<ContentNote>>
    suspend fun find(id: String): ContentNote?
    suspend fun prepareForShare(sourceKey: String): ShareNotePreparation
    suspend fun saveOrReuse(draft: ContentNoteDraft): SaveNoteOutcome
    suspend fun moveToTrash(id: String, at: Instant): Boolean
    suspend fun restore(id: String): RestoreOutcome
    suspend fun deletePermanently(id: String): Boolean
    suspend fun purgeExpired(cutoff: Instant): Int
}
