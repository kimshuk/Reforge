package com.andrewkim.reforge.navigation

import android.net.Uri

object AppDestination {
    const val HOME_GRAPH = "home"
    const val HOME = "home/main"
    const val NOTES_GRAPH = "notes"
    const val NOTES = "notes/list"
    const val NOTE_PATTERN = "note/{noteId}"
    const val TRASH = "trash"
    const val SHARE_IMPORT = "share-import"

    fun note(noteId: String): String = "note/${Uri.encode(noteId)}"
}
