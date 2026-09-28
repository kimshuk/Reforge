package com.andrewkim.reforge.network

import kotlinx.coroutines.runBlocking
import kotlinx.serialization.SerializationException
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
        val request = server.takeRequest()
        assertEquals("POST", request.method)
        assertEquals("/v1/youtube/transcript", request.path)
        val body = request.body.readUtf8()
        assertTrue(body.contains("\"youtubeUrl\":\"$canonical\""))
        assertTrue(body.contains("\"title\":\"Shared title\""))
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

    companion object {
        private const val SUCCESS = """{"transcriptId":"11111111-1111-4111-8111-111111111111","videoId":"dQw4w9WgXcQ","canonicalYoutubeUrl":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","transcriptText":"Transcript text","languageCode":"en","language":"English","isGenerated":false}"""
    }
}
