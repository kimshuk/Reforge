package com.andrewkim.reforge.network

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.SerializationException
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class YoutubeTranscriptServiceTest {
    private lateinit var server: MockWebServer
    private val canonical = "https://www.youtube.com/watch?v=dQw4w9WgXcQ".toHttpUrl()

    @Before fun setUp() { server = MockWebServer().also { it.start() } }
    @After fun tearDown() { server.shutdown() }

    @Test fun postsOnlyTranscriptRequestAndDecodesEveryField() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody(SUCCESS))
        val client = YoutubeTranscriptService(server.url("/v1/"))
        val response = client.fetch(canonical, "Shared title")
        assertEquals(30_000, client.callTimeoutMillis)
        assertEquals(30_000, client.timedClient.connectTimeoutMillis)
        assertEquals(30_000, client.timedClient.readTimeoutMillis)
        assertEquals(30_000, client.timedClient.writeTimeoutMillis)
        assertFalse(client.timedClient.retryOnConnectionFailure)
        assertFalse(client.timedClient.followRedirects)
        assertFalse(client.timedClient.followSslRedirects)
        assertEquals(okhttp3.Authenticator.NONE, client.timedClient.authenticator)
        assertEquals(okhttp3.Authenticator.NONE, client.timedClient.proxyAuthenticator)
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/v1/youtube/transcript", request.path)
        val body = request.body.readUtf8()
        assertEquals("""{"youtubeUrl":"$canonical","title":"Shared title"}""", body)
        assertFalse(body.contains("analyze"))
        assertEquals(1, server.requestCount)
        assertEquals("11111111-1111-4111-8111-111111111111", response.transcriptId)
        assertEquals("dQw4w9WgXcQ", response.videoId)
        assertEquals(canonical.toString(), response.canonicalYoutubeUrl)
        assertEquals("Transcript text", response.transcriptText)
        assertEquals("en", response.languageCode)
        assertEquals("English", response.language)
        assertEquals(false, response.isGenerated)
    }

    @Test fun backendErrorCodeAndMessageArePreserved() {
        server.enqueue(MockResponse().setResponseCode(502).setBody(
            """{"error":{"code":"TRANSCRIPT_UNAVAILABLE","message":"No transcript"}}"""
        ))
        val error = assertThrows(ApiError.Backend::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
        assertEquals(502, error.statusCode)
        assertEquals("TRANSCRIPT_UNAVAILABLE", error.code)
        assertEquals("No transcript", error.backendMessage)
    }

    @Test fun responseAfterDefaultTenSecondReadWindowStillSucceeds() = runBlocking {
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(SUCCESS)
                .setHeadersDelay(10_500, TimeUnit.MILLISECONDS)
        )
        val result = YoutubeTranscriptService(server.url("/")).fetch(canonical, null)
        assertEquals("dQw4w9WgXcQ", result.videoId)
    }

    @Test fun cancellingInFlightTranscriptRequestStopsHttpCall() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val client = YoutubeTranscriptService(server.url("/"))
        val call = async(Dispatchers.IO) { client.fetch(canonical, null) }
        assertNotNull(server.takeRequest(5, TimeUnit.SECONDS))
        call.cancel(CancellationException("leave screen"))
        withTimeout(5_000) {
            call.join()
            while (client.timedClient.dispatcher.runningCallsCount() != 0) delay(10)
        }
        try {
            call.await()
            throw AssertionError("Expected caller cancellation")
        } catch (cancellation: CancellationException) {
            assertEquals("leave screen", cancellation.message)
        }
    }

    @Test fun malformedSuccessJsonFailsDecoding() {
        server.enqueue(MockResponse().setResponseCode(200).setBody("{broken"))
        assertThrows(SerializationException::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
    }

    @Test fun malformedErrorEnvelopeBecomesInvalidResponse() {
        server.enqueue(MockResponse().setResponseCode(500).setBody("oops"))
        val error = assertThrows(ApiError.InvalidResponse::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
        assertEquals(500, error.statusCode)
    }

    @Test fun retryableHttp408DoesNotReplayTranscriptPost() = assertNoHttpReplay(408)

    @Test fun retryableHttp503DoesNotReplayTranscriptPost() = assertNoHttpReplay(503)

    @Test fun redirectDoesNotReplayTranscriptPost() {
        server.enqueue(MockResponse().setResponseCode(307).addHeader("Location", "/other/transcript"))
        server.enqueue(MockResponse().setBody(SUCCESS))
        val error = assertThrows(ApiError.InvalidResponse::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
        assertEquals(307, error.statusCode)
        assertEquals(1, server.requestCount)
    }

    @Test fun authenticationDoesNotReplayTranscriptPost() {
        var authentications = 0
        val http = okhttp3.OkHttpClient.Builder().authenticator { _, response ->
            authentications++
            response.request.newBuilder().header("Authorization", "test credential").build()
        }.build()
        server.enqueue(MockResponse().setResponseCode(401).addHeader("WWW-Authenticate", "Basic"))
        server.enqueue(MockResponse().setBody(SUCCESS))
        val error = assertThrows(ApiError.InvalidResponse::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/"), http).fetch(canonical, null) }
        }
        assertEquals(401, error.statusCode)
        assertEquals(0, authentications)
        assertEquals(1, server.requestCount)
    }

    @Test fun droppedConnectionDoesNotReconnectAndReplayTranscriptPost() {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
        server.enqueue(MockResponse().setBody(SUCCESS))
        assertThrows(java.io.IOException::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
        assertEquals(1, server.requestCount)
    }

    private fun assertNoHttpReplay(status: Int) {
        server.enqueue(MockResponse().setResponseCode(status).addHeader("Retry-After", "0")
            .setBody("""{"error":{"code":"UNAVAILABLE","message":"Wait"}}"""))
        server.enqueue(MockResponse().setBody(SUCCESS))
        val error = assertThrows(ApiError.Backend::class.java) {
            runBlocking { YoutubeTranscriptService(server.url("/")).fetch(canonical, null) }
        }
        assertEquals(status, error.statusCode)
        assertEquals(1, server.requestCount)
    }

    companion object {
        private const val SUCCESS = """{"transcriptId":"11111111-1111-4111-8111-111111111111","videoId":"dQw4w9WgXcQ","canonicalYoutubeUrl":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","transcriptText":"Transcript text","languageCode":"en","language":"English","isGenerated":false}"""
    }
}
