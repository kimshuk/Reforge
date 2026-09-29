package com.andrewkim.reforge.network

import kotlinx.serialization.Serializable
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.http.GET
import retrofit2.http.Query

sealed interface YouTubeAvailability {
    data class Available(val title: String) : YouTubeAvailability
    data class Unavailable(val reason: VideoUnavailableReason) : YouTubeAvailability
}

enum class VideoUnavailableReason(val userMessage: String) {
    PRIVATE_OR_RESTRICTED("This video is private or restricted."),
    NOT_FOUND_OR_REMOVED("This video was removed or is not found."),
    RATE_LIMITED("YouTube is rate-limiting checks right now. Please try again."),
    UNKNOWN("Unable to verify YouTube video availability."),
}

fun interface YouTubeAvailabilityChecking {
    suspend fun check(canonicalUrl: HttpUrl): YouTubeAvailability
}

internal interface YouTubeOEmbedApi {
    @GET("oembed")
    suspend fun fetch(@Query("url") url: String, @Query("format") format: String = "json"):
        Response<ResponseBody>
}

@Serializable
private data class OEmbedResponse(val title: String)

class YouTubeAvailabilityService(
    baseUrl: HttpUrl = DEFAULT_OEMBED_BASE_URL,
    client: OkHttpClient = OkHttpClient(),
    private val json: Json = Json { ignoreUnknownKeys = true },
) : YouTubeAvailabilityChecking {
    private val api = Retrofit.Builder().baseUrl(baseUrl).client(client)
        .build().create(YouTubeOEmbedApi::class.java)

    override suspend fun check(canonicalUrl: HttpUrl): YouTubeAvailability {
        val response = api.fetch(canonicalUrl.toString())
        if (!response.isSuccessful) {
            val reason = when (response.code()) {
                401 -> VideoUnavailableReason.PRIVATE_OR_RESTRICTED
                404 -> VideoUnavailableReason.NOT_FOUND_OR_REMOVED
                429 -> VideoUnavailableReason.RATE_LIMITED
                else -> VideoUnavailableReason.UNKNOWN
            }
            response.errorBody()?.close()
            return YouTubeAvailability.Unavailable(reason)
        }
        val raw = response.body()?.use { it.string() }
            ?: throw ApiError.InvalidResponse(response.code())
        return YouTubeAvailability.Available(json.decodeFromString<OEmbedResponse>(raw).title)
    }

    companion object {
        val DEFAULT_OEMBED_BASE_URL: HttpUrl =
            "https://www.youtube.com/".toHttpUrl()
    }
}
