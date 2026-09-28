package com.andrewkim.reforge.network

import java.util.concurrent.TimeUnit
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Retrofit

interface YoutubeTranscriptFetching {
    suspend fun fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse
}

class YoutubeTranscriptService(
    baseUrl: HttpUrl,
    client: OkHttpClient = OkHttpClient(),
    private val json: Json = Json,
) : YoutubeTranscriptFetching {
    private val timedClient = client.newBuilder().callTimeout(30, TimeUnit.SECONDS).build()
    val callTimeoutMillis: Int = timedClient.callTimeoutMillis
    private val api = Retrofit.Builder().baseUrl(baseUrl).client(timedClient)
        .build().create(ReforgeApi::class.java)

    override suspend fun fetch(canonicalUrl: HttpUrl, title: String?): YoutubeTranscriptResponse {
        val body = json.encodeToString(YoutubeTranscriptRequest(canonicalUrl.toString(), title))
            .toRequestBody("application/json".toMediaType())
        val response = api.transcript(body)
        val raw = if (response.isSuccessful) response.body()?.use { it.string() }
            else response.errorBody()?.use { it.string() }
        if (!response.isSuccessful) {
            val backend = runCatching {
                json.decodeFromString<BackendErrorEnvelope>(raw.orEmpty()).error
            }.getOrNull()
            if (backend != null) throw ApiError.Backend(response.code(), backend.code, backend.message)
            throw ApiError.InvalidResponse(response.code())
        }
        return json.decodeFromString<YoutubeTranscriptResponse>(
            raw ?: throw ApiError.InvalidResponse(response.code())
        )
    }
}
