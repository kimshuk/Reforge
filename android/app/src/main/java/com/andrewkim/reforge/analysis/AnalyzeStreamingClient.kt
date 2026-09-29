package com.andrewkim.reforge.analysis

import java.io.IOException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerializationException
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

@Serializable
data class AnalyzeProgressUpdate(val stage: String, val message: String)

sealed class AnalyzeApiError(message: String) : Exception(message) {
    data class Backend(
        val statusCode: Int,
        val code: String,
        val backendMessage: String,
        val videoId: String? = null,
    ) : AnalyzeApiError(backendMessage)

    data class Http(val statusCode: Int) : AnalyzeApiError("Analysis HTTP error ($statusCode)")
    data class InvalidResponse(val event: String?) : AnalyzeApiError("Invalid analysis response")
    data object MissingResult : AnalyzeApiError("Analysis stream ended without a result")
    data class Transport(val failure: IOException) : AnalyzeApiError("Analysis connection failed")
}

@Serializable
private data class BackendErrorEnvelope(val error: BackendErrorPayload)

@Serializable
private data class BackendErrorPayload(val code: String, val message: String, val videoId: String? = null)

@Serializable
private data class StreamErrorPayload(
    val stage: String,
    val statusCode: Int,
    val code: String,
    val message: String,
)

class AnalyzeStreamingClient(
    private val baseUrl: HttpUrl,
    private val client: OkHttpClient = OkHttpClient(),
    private val json: Json = Json { ignoreUnknownKeys = true; encodeDefaults = true },
) {
    suspend fun analyze(
        request: AnalyzeRequest,
        onProgress: (AnalyzeProgressUpdate) -> Unit = {},
    ): AnalyzeResponse = withContext(Dispatchers.IO) {
        val endpoint = baseUrl.newBuilder().addPathSegment("analyze")
            .addQueryParameter("stream", "progress").build()
        val httpRequest = Request.Builder().url(endpoint)
            .header("Accept", "text/event-stream")
            .post(json.encodeToString(request).toRequestBody("application/json".toMediaType()))
            .build()
        val call = client.newCall(httpRequest)
        val cancellationWatcher = launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                call.cancel()
            }
        }
        try {
            call.execute().use { response ->
                val body = response.body
                if (!response.isSuccessful) {
                    val error = runCatching {
                        json.decodeFromString<BackendErrorEnvelope>(body.string()).error
                    }.getOrNull()
                    if (error != null) throw AnalyzeApiError.Backend(
                        response.code, error.code, error.message, error.videoId,
                    )
                    throw AnalyzeApiError.Http(response.code)
                }
                if (!response.header("Content-Type").orEmpty().contains("text/event-stream", ignoreCase = true)) {
                    return@withContext decodeResult(body.string())
                }
                val source = body.source()
                var event = "message"
                val data = mutableListOf<String>()
                fun dispatch(): AnalyzeResponse? {
                    if (data.isEmpty()) {
                        if (event in setOf("started", "progress", "completed", "result", "error")) {
                            throw AnalyzeApiError.InvalidResponse(event)
                        }
                        return null
                    }
                    val payload = data.joinToString("\n")
                    return when (event) {
                        "started", "progress", "completed" -> {
                            val update = decodeKnown(event) {
                                json.decodeFromString<AnalyzeProgressUpdate>(payload)
                            }
                            onProgress(update)
                            null
                        }
                        "result" -> decodeResult(payload)
                        "error" -> {
                            val error = decodeKnown(event) {
                                json.decodeFromString<StreamErrorPayload>(payload)
                            }
                            throw AnalyzeApiError.Backend(error.statusCode, error.code, error.message)
                        }
                        else -> null
                    }
                }
                while (true) {
                    currentCoroutineContext().ensureActive()
                    val line = source.readUtf8Line() ?: break
                    if (line.isEmpty()) {
                        val result = dispatch()
                        if (result != null) return@withContext result
                        event = "message"
                        data.clear()
                        continue
                    }
                    if (line.startsWith(':')) continue
                    val separator = line.indexOf(':')
                    val name = if (separator < 0) line else line.substring(0, separator)
                    val value = if (separator < 0) "" else line.substring(separator + 1).removePrefix(" ")
                    when (name) {
                        "event" -> event = value
                        "data" -> data.add(value)
                    }
                }
                currentCoroutineContext().ensureActive()
                dispatch() ?: throw AnalyzeApiError.MissingResult
            }
        } catch (error: IOException) {
            currentCoroutineContext().ensureActive()
            throw AnalyzeApiError.Transport(error)
        } finally {
            cancellationWatcher.cancel()
            call.cancel()
        }
    }

    private fun decodeResult(payload: String): AnalyzeResponse = decodeKnown("result") {
        try {
            json.decodeAnalyzeResponse(payload)
        } catch (direct: SerializationException) {
            val objectValue = json.parseToJsonElement(payload).jsonObject
            val nested = objectValue["data"] ?: objectValue["result"] ?: throw direct
            json.decodeAnalyzeResponse(nested.toString())
        }
    }

    private inline fun <T> decodeKnown(event: String, decode: () -> T): T = try {
        decode()
    } catch (error: AnalyzeApiError) {
        throw error
    } catch (error: Exception) {
        throw AnalyzeApiError.InvalidResponse(event)
    }
}
