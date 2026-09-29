package com.andrewkim.reforge.notes

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import java.time.Instant

@Entity(tableName = "content_notes", indices = [Index(value = ["sourceKey"], unique = true)])
data class ContentNoteEntity(
    @PrimaryKey val id: String,
    val sourceKey: String,
    val sourceType: String,
    val videoId: String,
    val sourceUrl: String,
    val canonicalUrl: String,
    val title: String,
    val transcriptId: String,
    val transcriptText: String,
    val transcriptLanguageCode: String?,
    val transcriptIsGenerated: Boolean?,
    val createdAt: Instant,
    val trashedAt: Instant?,
) {
    fun toDomain() = ContentNote(
        id, sourceKey, sourceType, videoId, sourceUrl, canonicalUrl, title,
        transcriptId, transcriptText, transcriptLanguageCode, transcriptIsGenerated,
        createdAt, trashedAt,
    )

    companion object {
        fun fromDraft(draft: ContentNoteDraft) = ContentNoteEntity(
            draft.id, draft.sourceKey, draft.sourceType, draft.videoId, draft.sourceUrl,
            draft.canonicalUrl, draft.title, draft.transcriptId, draft.transcriptText,
            draft.transcriptLanguageCode, draft.transcriptIsGenerated, draft.createdAt, null,
        )
    }
}
