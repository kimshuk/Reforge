package com.andrewkim.reforge.network

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.HttpUrl

interface ShareTitleResolving {
    suspend fun resolve(canonicalUrl: HttpUrl): String?
}

class ShareTitleResolver(
    private val availability: YouTubeAvailabilityChecking = YouTubeAvailabilityService(),
    private val timeoutMillis: Long = 1_500,
) : ShareTitleResolving {
    override suspend fun resolve(canonicalUrl: HttpUrl): String? = try {
        withTimeoutOrNull(timeoutMillis) {
            when (val result = availability.check(canonicalUrl)) {
                is YouTubeAvailability.Available -> result.title.trim().takeIf(String::isNotEmpty)
                is YouTubeAvailability.Unavailable -> null
            }
        }
    } catch (cancellation: CancellationException) {
        throw cancellation
    } catch (_: Exception) {
        null
    }
}
