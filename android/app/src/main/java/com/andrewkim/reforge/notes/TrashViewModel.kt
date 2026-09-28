package com.andrewkim.reforge.notes

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.time.Clock
import java.time.Duration
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TrashViewModel(
    private val repository: ContentNoteRepository,
    private val clock: Clock = Clock.systemUTC(),
) : ViewModel() {
    private val mutableNotes = MutableStateFlow<List<ContentNote>?>(null)
    val notes = mutableNotes.asStateFlow()
    private var observeJob: Job? = null

    fun enter() {
        if (observeJob?.isActive == true) return
        observeJob = viewModelScope.launch {
            purge()
            repository.observeTrash().collect { mutableNotes.value = it }
        }
    }

    fun onResume() {
        if (observeJob?.isActive != true) { enter(); return }
        viewModelScope.launch { purge() }
    }

    private suspend fun purge() {
        try {
            repository.purgeExpired(clock.instant().minus(Duration.ofDays(30)))
        } catch (error: CancellationException) {
            throw error
        } catch (_: Exception) {
            // Retain rows; next entry or resume will retry.
        }
    }

    fun restore(id: String) {
        viewModelScope.launch { runCatching { repository.restore(id) } }
    }

    fun deletePermanently(id: String) {
        viewModelScope.launch { runCatching { repository.deletePermanently(id) } }
    }
}
