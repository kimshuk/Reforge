package com.andrewkim.reforge.sharing

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class ShareImportViewModel(
    private val ingestor: ShareIngesting,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel() {
    private var generation: Long = savedStateHandle[KEY_GENERATION] ?: 0L
    private var job: Job? = null
    private val mutableState = MutableStateFlow(restoredState())
    val state = mutableState.asStateFlow()

    fun accept(input: SharedTextResult) {
        job?.cancel()
        generation += 1
        savedStateHandle[KEY_GENERATION] = generation
        clearPersistedOutcome()
        val current = generation
        if (input !is SharedTextResult.Valid) {
            mutableState.value = ShareImportState.Error(current, INVALID_URL_COPY)
            return
        }
        mutableState.value = ShareImportState.Loading(current)
        job = viewModelScope.launch {
            try {
                applyResult(current, ingestor.ingest(input))
            } catch (_: CancellationException) {
                // A later generation or explicit cancellation owns the visible state.
            } catch (failure: ShareIngestionFailure) {
                setError(current, failure.messageForUser())
            } catch (_: Exception) {
                setError(current, STORAGE_COPY)
            }
        }
    }

    fun confirmRestore() {
        val awaiting = mutableState.value as? ShareImportState.AwaitingRestore ?: return
        if (awaiting.generation != generation) return
        mutableState.value = ShareImportState.Loading(generation, awaiting.noteId)
        job = viewModelScope.launch {
            try {
                applyResult(awaiting.generation, ingestor.restore(awaiting.noteId))
            } catch (_: CancellationException) {
                // Cancellation makes this generation terminal.
            } catch (failure: ShareIngestionFailure) {
                setError(awaiting.generation, failure.messageForUser())
            } catch (_: Exception) {
                setError(awaiting.generation, STORAGE_COPY)
            }
        }
    }

    fun cancelRestore() {
        when (val current = mutableState.value) {
            is ShareImportState.AwaitingRestore -> finish(current.generation)
            is ShareImportState.Loading -> if (current.restoringNoteId != null) finish(current.generation)
            else -> Unit
        }
    }

    fun cancelImport() {
        val current = mutableState.value as? ShareImportState.Active ?: return
        if (current is ShareImportState.Completed || current is ShareImportState.Finished) return
        finish(current.generation)
    }

    fun abandonForGeneralLaunch() {
        val current = mutableState.value as? ShareImportState.Active ?: return
        if (current !is ShareImportState.Finished) finish(current.generation)
    }

    fun acknowledgeDetailOpened(generation: Long, noteId: String) {
        val completed = mutableState.value as? ShareImportState.Completed ?: return
        if (generation != this.generation || completed.generation != generation ||
            completed.noteId != noteId || completed.navigationAcknowledged
        ) return
        publish(completed.copy(navigationAcknowledged = true))
    }

    private fun applyResult(generation: Long, result: ShareIngestionResult) {
        if (!canUpdate(generation)) return
        when (result) {
            is ShareIngestionResult.RestoreRequired ->
                mutableState.value = ShareImportState.AwaitingRestore(generation, result.noteId)
            is ShareIngestionResult.Saved, is ShareIngestionResult.AlreadySaved ->
                publish(ShareImportState.Completed(generation, result.noteId))
        }
    }

    private fun setError(generation: Long, message: String) {
        if (canUpdate(generation)) mutableState.value = ShareImportState.Error(generation, message)
    }

    private fun canUpdate(generation: Long): Boolean =
        this.generation == generation && mutableState.value.let {
            it is ShareImportState.Loading && it.generation == generation
        }

    private fun finish(generation: Long) {
        if (generation != this.generation || mutableState.value is ShareImportState.Finished) return
        job?.cancel()
        publish(ShareImportState.Finished(generation))
    }

    private fun publish(outcome: ShareImportState.Active) {
        when (outcome) {
            is ShareImportState.Completed -> {
                savedStateHandle[KEY_OUTCOME] = OUTCOME_COMPLETED
                savedStateHandle[KEY_NOTE_ID] = outcome.noteId
                savedStateHandle[KEY_ACKNOWLEDGED] = outcome.navigationAcknowledged
            }
            is ShareImportState.Finished -> {
                savedStateHandle[KEY_OUTCOME] = OUTCOME_FINISHED
                savedStateHandle.remove<String>(KEY_NOTE_ID)
                savedStateHandle.remove<Boolean>(KEY_ACKNOWLEDGED)
            }
            else -> Unit
        }
        mutableState.value = outcome
    }

    private fun restoredState(): ShareImportState = when (savedStateHandle.get<String>(KEY_OUTCOME)) {
        OUTCOME_COMPLETED -> savedStateHandle.get<String>(KEY_NOTE_ID)?.let {
            ShareImportState.Completed(generation, it, savedStateHandle[KEY_ACKNOWLEDGED] ?: false)
        } ?: ShareImportState.Idle
        OUTCOME_FINISHED -> ShareImportState.Finished(generation)
        else -> ShareImportState.Idle
    }

    private fun clearPersistedOutcome() {
        savedStateHandle.remove<String>(KEY_OUTCOME)
        savedStateHandle.remove<String>(KEY_NOTE_ID)
        savedStateHandle.remove<Boolean>(KEY_ACKNOWLEDGED)
    }

    private fun ShareIngestionFailure.messageForUser(): String = when (this) {
        ShareIngestionFailure.InvalidIdentity, ShareIngestionFailure.IdentityMismatch -> INVALID_URL_COPY
        ShareIngestionFailure.TranscriptUnavailable -> TRANSCRIPT_UNAVAILABLE_COPY
        ShareIngestionFailure.Provider -> PROVIDER_COPY
        ShareIngestionFailure.Storage -> STORAGE_COPY
    }

    private companion object {
        const val KEY_GENERATION = "share_import_generation"
        const val KEY_OUTCOME = "share_import_outcome"
        const val KEY_NOTE_ID = "share_import_note_id"
        const val KEY_ACKNOWLEDGED = "share_import_navigation_acknowledged"
        const val OUTCOME_COMPLETED = "completed"
        const val OUTCOME_FINISHED = "finished"
        const val INVALID_URL_COPY = "Please enter a valid YouTube URL."
        const val TRANSCRIPT_UNAVAILABLE_COPY = "The video is available, but transcript is not available."
        const val PROVIDER_COPY = "Transcript provider failed. Please try again."
        const val STORAGE_COPY = "Couldn’t save this video. Please try again."
    }
}
