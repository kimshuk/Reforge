package com.andrewkim.reforge.notes

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.time.Clock
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

sealed interface NoteDetailState {
    data object Loading : NoteDetailState
    data object Missing : NoteDetailState
    data class Ready(val note: ContentNote) : NoteDetailState
}

class NoteDetailViewModel(
    private val repository: ContentNoteRepository,
    private val noteId: String,
    private val clock: Clock = Clock.systemUTC(),
) : ViewModel() {
    private val mutableState = MutableStateFlow<NoteDetailState>(NoteDetailState.Loading)
    val state = mutableState.asStateFlow()

    init {
        viewModelScope.launch {
            repository.observeActive().map { notes -> notes.firstOrNull { it.id == noteId } }
                .collect { note ->
                    mutableState.value = note?.let(NoteDetailState::Ready) ?: NoteDetailState.Missing
                }
        }
    }

    fun moveToTrash() {
        viewModelScope.launch { runCatching { repository.moveToTrash(noteId, clock.instant()) } }
    }
}
