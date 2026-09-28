package com.andrewkim.reforge.sharing

import com.andrewkim.reforge.network.ApiError
import com.andrewkim.reforge.network.ShareTitleResolving
import com.andrewkim.reforge.network.YoutubeTranscriptFetching
import com.andrewkim.reforge.notes.ContentNoteDraft
import com.andrewkim.reforge.notes.ContentNoteRepository
import com.andrewkim.reforge.notes.RestoreOutcome
import com.andrewkim.reforge.notes.SaveNoteOutcome
import com.andrewkim.reforge.notes.ShareNotePreparation
import java.time.Instant
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive

sealed interface ShareIngestionResult {
    val noteId: String

    data class Saved(override val noteId: String) : ShareIngestionResult
    data class AlreadySaved(override val noteId: String) : ShareIngestionResult
    data class RestoreRequired(override val noteId: String) : ShareIngestionResult
}

sealed class ShareIngestionFailure : Exception() {
    data object InvalidIdentity : ShareIngestionFailure()
    data object IdentityMismatch : ShareIngestionFailure()
    data object TranscriptUnavailable : ShareIngestionFailure()
    data object Provider : ShareIngestionFailure()
    data object Storage : ShareIngestionFailure()
}

interface ShareIngesting {
    suspend fun ingest(input: SharedTextResult.Valid): ShareIngestionResult
    suspend fun restore(noteId: String): ShareIngestionResult
}

class ShareIngestionCoordinator(
    private val repository: ContentNoteRepository,
    private val transcriptService: YoutubeTranscriptFetching,
    private val titleResolver: ShareTitleResolving,
    private val now: () -> Instant = Instant::now,
) : ShareIngesting {
    override suspend fun ingest(input: SharedTextResult.Valid): ShareIngestionResult {
        currentCoroutineContext().ensureActive()
        val identity = YouTubeVideoIdentity.parse(input.sourceUrl).getOrNull()
            ?: throw ShareIngestionFailure.InvalidIdentity
        if (identity != input.identity) throw ShareIngestionFailure.InvalidIdentity

        when (val prepared = storage { repository.prepareForShare(identity.sourceKey) }) {
            is ShareNotePreparation.Active -> return ShareIngestionResult.AlreadySaved(prepared.note.id)
            is ShareNotePreparation.Trashed -> return ShareIngestionResult.RestoreRequired(prepared.note.id)
            ShareNotePreparation.Absent -> Unit
        }

        val sharedTitle = input.sharedTitle?.trim()?.takeIf(String::isNotEmpty)
        val (transcript, metadataTitle) = coroutineScope {
            val transcriptTask = async {
                provider { transcriptService.fetch(identity.canonicalUrl, sharedTitle) }
            }
            val titleTask = if (sharedTitle == null) async {
                try {
                    titleResolver.resolve(identity.canonicalUrl)?.trim()?.takeIf(String::isNotEmpty)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    null
                }
            } else null
            transcriptTask.await() to titleTask?.await()
        }
        if (transcript.videoId != identity.videoId) throw ShareIngestionFailure.IdentityMismatch
        currentCoroutineContext().ensureActive()

        val draft = ContentNoteDraft(
            sourceKey = identity.sourceKey,
            sourceType = "youtube",
            videoId = identity.videoId,
            sourceUrl = input.sourceUrl,
            canonicalUrl = identity.canonicalUrl.toString(),
            title = sharedTitle ?: metadataTitle ?: identity.canonicalUrl.toString(),
            transcriptId = transcript.transcriptId,
            transcriptText = transcript.transcriptText,
            transcriptLanguageCode = transcript.languageCode,
            transcriptIsGenerated = transcript.isGenerated,
            createdAt = now(),
        )
        return when (val outcome = storage { repository.saveOrReuse(draft) }) {
            is SaveNoteOutcome.Saved -> ShareIngestionResult.Saved(outcome.note.id)
            is SaveNoteOutcome.AlreadySaved -> ShareIngestionResult.AlreadySaved(outcome.note.id)
            is SaveNoteOutcome.RestoreRequired -> ShareIngestionResult.RestoreRequired(outcome.note.id)
        }
    }

    override suspend fun restore(noteId: String): ShareIngestionResult {
        currentCoroutineContext().ensureActive()
        return when (val outcome = storage { repository.restore(noteId) }) {
            is RestoreOutcome.Restored -> ShareIngestionResult.AlreadySaved(outcome.note.id)
            is RestoreOutcome.AlreadyActive -> ShareIngestionResult.AlreadySaved(outcome.note.id)
            RestoreOutcome.Missing -> throw ShareIngestionFailure.Storage
        }
    }

    private suspend fun <T> storage(block: suspend () -> T): T = try {
        block()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (_: Exception) {
        throw ShareIngestionFailure.Storage
    }

    private suspend fun <T> provider(block: suspend () -> T): T = try {
        block()
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (error: ApiError.Backend) {
        when (error.code) {
            "INVALID_YOUTUBE_URL", "YOUTUBE_URL_INVALID" -> throw ShareIngestionFailure.InvalidIdentity
            "TRANSCRIPT_UNAVAILABLE", "EMPTY_TRANSCRIPT" -> throw ShareIngestionFailure.TranscriptUnavailable
            else -> throw ShareIngestionFailure.Provider
        }
    } catch (_: Exception) {
        throw ShareIngestionFailure.Provider
    }
}
