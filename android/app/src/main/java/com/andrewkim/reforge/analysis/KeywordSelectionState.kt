package com.andrewkim.reforge.analysis

/** Selection is scoped to category and occurrence, never to the backend's optional IDs. */
data class KeywordOccurrence(val categoryIndex: Int, val keywordIndex: Int)

data class KeywordSelectionState(
    val levels: Map<KeywordOccurrence, Int> = emptyMap(),
) {
    fun isSelected(key: KeywordOccurrence): Boolean = key in levels
    fun level(key: KeywordOccurrence): Int = levels[key] ?: 1
    fun select(key: KeywordOccurrence): KeywordSelectionState = copy(levels = levels + (key to 1))
    fun advanceLevel(key: KeywordOccurrence): KeywordSelectionState =
        if (key in levels) copy(levels = levels + (key to (level(key) + 1).coerceAtMost(3))) else this
    fun remove(key: KeywordOccurrence): KeywordSelectionState = copy(levels = levels - key)
}
