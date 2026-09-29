package com.andrewkim.reforge.notes

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import java.time.Clock
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class NotesListViewModel(
    private val repository: ContentNoteRepository,
    private val clock: Clock = Clock.systemUTC(),
) : ViewModel() {
    private val mutableNotes = MutableStateFlow<List<ContentNote>?>(null)
    val notes = mutableNotes.asStateFlow()

    init {
        viewModelScope.launch { repository.observeActive().collect { mutableNotes.value = it } }
    }

    fun moveToTrash(id: String) {
        viewModelScope.launch { runCatching { repository.moveToTrash(id, clock.instant()) } }
    }
}
