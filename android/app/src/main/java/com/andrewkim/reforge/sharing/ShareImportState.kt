package com.andrewkim.reforge.sharing

sealed interface ShareImportState {
    data object Idle : ShareImportState

    sealed interface Active : ShareImportState {
        val generation: Long
    }

    data class Loading(
        override val generation: Long,
        val restoringNoteId: String? = null,
    ) : Active

    data class AwaitingRestore(
        override val generation: Long,
        val noteId: String,
    ) : Active

    data class Error(
        override val generation: Long,
        val message: String,
    ) : Active

    data class Completed(
        override val generation: Long,
        val noteId: String,
        val navigationAcknowledged: Boolean = false,
    ) : Active

    data class Finished(override val generation: Long) : Active
}
