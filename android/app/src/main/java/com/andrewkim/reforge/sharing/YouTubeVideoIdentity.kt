package com.andrewkim.reforge.sharing

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

data class YouTubeVideoIdentity(
    val videoId: String,
    val canonicalUrl: HttpUrl,
    val sourceKey: String,
) {
    companion object {
        private val videoIdPattern = Regex("^[A-Za-z0-9_-]{11}$")

        fun parse(rawUrl: String): Result<YouTubeVideoIdentity> = runCatching {
            val url = requireNotNull(rawUrl.toHttpUrlOrNull()) { "Invalid YouTube URL" }
            require(url.scheme == "http" || url.scheme == "https")
            require(url.username.isEmpty() && url.password.isEmpty())

            val videoId = when (url.host) {
                "youtube.com", "www.youtube.com", "m.youtube.com" -> when {
                    url.encodedPath == "/watch" -> url.queryParameter("v")
                    url.pathSegments.size == 2 && url.pathSegments[0] == "shorts" ->
                        url.pathSegments[1]
                    else -> null
                }
                "youtu.be" -> url.pathSegments.singleOrNull()
                else -> null
            }
            require(videoId != null && videoIdPattern.matches(videoId)) { "Invalid YouTube video ID" }
            val canonical = requireNotNull(
                "https://www.youtube.com/watch?v=$videoId".toHttpUrlOrNull()
            )
            YouTubeVideoIdentity(videoId, canonical, "youtube:$videoId")
        }
    }
}
