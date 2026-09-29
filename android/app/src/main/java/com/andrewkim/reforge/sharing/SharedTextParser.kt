package com.andrewkim.reforge.sharing

sealed interface SharedTextResult {
    data class Valid(
        val identity: YouTubeVideoIdentity,
        val sourceUrl: String,
        val sharedTitle: String?,
    ) : SharedTextResult

    data object Invalid : SharedTextResult
    data object Ambiguous : SharedTextResult
}

object SharedTextParser {
    private val urlPattern = Regex("https?://[^\\s<>\\\"']+", RegexOption.IGNORE_CASE)
    private val trailingPunctuation = charArrayOf('.', ',', '!', '?', ';', ':', ')', ']', '}')

    fun parse(text: CharSequence): SharedTextResult {
        val input = text.toString()
        val candidates = urlPattern.findAll(input).mapNotNull { match ->
            val raw = match.value.trimEnd(*trailingPunctuation)
            YouTubeVideoIdentity.parse(raw).getOrNull()?.let { match.range.first to (raw to it) }
        }.toList()
        if (candidates.isEmpty()) return SharedTextResult.Invalid
        if (candidates.map { it.second.second.videoId }.distinct().size > 1) {
            return SharedTextResult.Ambiguous
        }
        val (offset, pair) = candidates.first()
        val title = urlPattern.replace(input.substring(0, offset), "").trim().takeIf { it.isNotEmpty() }
        return SharedTextResult.Valid(pair.second, pair.first, title)
    }
}
