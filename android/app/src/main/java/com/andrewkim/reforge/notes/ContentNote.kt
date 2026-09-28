package com.andrewkim.reforge.notes

import java.time.Instant
import java.util.UUID

data class ContentNoteDraft(
    val id: String = UUID.randomUUID().toString(),
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
)

data class ContentNote(
    val id: String,
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
)

sealed interface ShareNotePreparation {
    data class Active(val note: ContentNote) : ShareNotePreparation
    data class Trashed(val note: ContentNote) : ShareNotePreparation
    data object Absent : ShareNotePreparation
}

sealed interface SaveNoteOutcome {
    data class Saved(val note: ContentNote) : SaveNoteOutcome
    data class AlreadySaved(val note: ContentNote) : SaveNoteOutcome
    data class RestoreRequired(val note: ContentNote) : SaveNoteOutcome
}

sealed interface RestoreOutcome {
    data class Restored(val note: ContentNote) : RestoreOutcome
    data class AlreadyActive(val note: ContentNote) : RestoreOutcome
    data object Missing : RestoreOutcome
}
