package com.andrewkim.reforge.analysis

import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class AnalyzeStreamingClientTest {
    private lateinit var server: MockWebServer
    private val request = AnalyzeRequest(title = "영상 제목", youtubeUrl = "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    @Before fun setUp() { server = MockWebServer().also { it.start() } }
    @After fun tearDown() { server.shutdown() }

    @Test fun postsExactYoutubeJsonAndDeliversOrderedProgressAcrossFragmentedUnicodeFrames() = runBlocking {
        server.enqueue(stream(
            "event: started\r\ndata: {\"stage\":\"started\",\"message\":\"시작 😀\",\"type\":\"youtube\"}\r\n\r\n" +
                "event: future\r\ndata: {malformed}\r\n\r\n" +
                "event: progress\r\ndata: {\"stage\":\"fetching_transcript\",\"message\":\"자막\"}\r\n\r\n" +
                "event: completed\r\ndata: {\"stage\":\"completed\",\"message\":\"완료\"}\r\n\r\n" +
                "event: result\r\ndata: $MODERN\r\n\r\n",
        ).throttleBody(1, 1, TimeUnit.MILLISECONDS))
        val progress = mutableListOf<AnalyzeProgressUpdate>()
        val result = client().analyze(request) { progress.add(it) }
        val recorded = server.takeRequest()
        assertEquals("POST", recorded.method)
        assertEquals("/v1/analyze?stream=progress", recorded.path)
        assertEquals("text/event-stream", recorded.getHeader("Accept"))
        assertEquals("application/json; charset=utf-8", recorded.getHeader("Content-Type"))
        assertEquals("""{"type":"youtube","title":"영상 제목","youtubeUrl":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}""", recorded.body.readUtf8())
        assertEquals(listOf("started", "fetching_transcript", "completed"), progress.map { it.stage })
        assertEquals("시작 😀", progress[0].message)
        assertEquals("영상", result.categories[0].title)
        assertEquals(1, server.requestCount)
    }

    @Test fun preservesSameTermOccurrencesAndTheirOwnCitationsAndSources() = runBlocking {
        server.enqueue(stream("event: result\ndata: $MODERN\n\n"))
        val category = client().analyze(request).categories.single()
        assertEquals("server-category", category.id)
        assertEquals(listOf("Codex", "Codex"), category.keywords.map { it.term })
        assertEquals(listOf("occurrence-1", "occurrence-2"), category.keywords.map { it.id })
        assertEquals(listOf("https://example.com?t=46s", "https://example.com?t=312s"), category.keywords.map { it.source.ref })
        assertEquals(listOf("https://example.com?t=46s", "https://example.com?t=47s"), category.keywords[0].sources.map { it.ref })
        assertEquals(listOf("C1"), category.keywords[0].externalSourcesForLevel(2).map { it.citationId })
        assertEquals(listOf("C2"), category.keywords[1].externalSourcesForLevel(3).map { it.citationId })
        assertTrue(category.keywords[1].externalSourcesForLevel(2).isEmpty())
    }

    @Test fun legacyIdentityUsesTranscriptCategoryAndKeywordIndexesAndMissingCollectionsDefault() = runBlocking {
        server.enqueue(stream("event: result\ndata: $LEGACY\n\n"))
        val result = client().analyze(request)
        val categories = result.categories
        assertEquals(listOf("legacy:category:0", "legacy:category:1"), categories.map { it.id })
        assertEquals(listOf("legacy:category:0:keyword:0", "legacy:category:0:keyword:1"), categories[0].keywords.map { it.id })
        assertEquals("legacy:category:1:keyword:0", categories[1].keywords.single().id)
        assertEquals(categories[0].keywords[0].source, categories[0].keywords[0].sources.single())
        assertTrue(categories[0].keywords[0].level2CitationIds.isEmpty())
        assertTrue(categories[0].keywords[0].level3CitationIds.isEmpty())
        assertTrue(categories[0].keywords[0].externalSources.isEmpty())
    }

    @Test fun backendSseErrorIsTypedAndDoesNotRetry() {
        server.enqueue(stream("event: error\ndata: {\"stage\":\"error\",\"statusCode\":429,\"code\":\"OPENAI_QUOTA_OR_RATE_LIMIT\",\"message\":\"Busy\"}\n\n"))
        val error = assertThrows(AnalyzeApiError.Backend::class.java) {
            runBlocking { client().analyze(request) }
        }
        assertEquals(429, error.statusCode)
        assertEquals("OPENAI_QUOTA_OR_RATE_LIMIT", error.code)
        assertEquals("Busy", error.backendMessage)
        assertEquals(1, server.requestCount)
    }

    @Test fun httpErrorEnvelopeIsTyped() {
        server.enqueue(MockResponse().setResponseCode(400).setBody("""{"error":{"code":"INVALID_YOUTUBE_URL","message":"Invalid URL","videoId":"bad"}}"""))
        val error = assertThrows(AnalyzeApiError.Backend::class.java) {
            runBlocking { client().analyze(request) }
        }
        assertEquals(400, error.statusCode)
        assertEquals("INVALID_YOUTUBE_URL", error.code)
        assertEquals("bad", error.videoId)
    }

    @Test fun malformedKnownEventFailsEvenWhenLaterResultExists() {
        server.enqueue(stream("event: progress\ndata: {broken}\n\nevent: result\ndata: $MODERN\n\n"))
        val error = assertThrows(AnalyzeApiError.InvalidResponse::class.java) {
            runBlocking { client().analyze(request) }
        }
        assertEquals("progress", error.event)
    }

    @Test fun emptyKnownEventFails() {
        server.enqueue(stream("event: result\n\n"))
        val error = assertThrows(AnalyzeApiError.InvalidResponse::class.java) {
            runBlocking { client().analyze(request) }
        }
        assertEquals("result", error.event)
    }

    @Test fun eofBeforeResultFailsWithoutRetry() {
        server.enqueue(stream("event: progress\ndata: {\"stage\":\"started\",\"message\":\"Accepted\"}\n\n"))
        assertThrows(AnalyzeApiError.MissingResult::class.java) {
            runBlocking { client().analyze(request) }
        }
        assertEquals(1, server.requestCount)
    }

    @Test fun streamingWaitOutlivesInjectedShortReadAndCallTimeouts() = runBlocking {
        server.enqueue(stream("event: result\ndata: $MODERN\n\n")
            .setBodyDelay(350, TimeUnit.MILLISECONDS))
        val shortTimeoutClient = okhttp3.OkHttpClient.Builder()
            .readTimeout(100, TimeUnit.MILLISECONDS)
            .callTimeout(150, TimeUnit.MILLISECONDS)
            .build()

        val result = client(shortTimeoutClient).analyze(request)

        assertEquals("transcript-1", result.transcriptId)
        assertEquals(1, server.requestCount)
    }

    @Test fun retryableHttp408DoesNotReplayAnalysisPost() {
        server.enqueue(MockResponse().setResponseCode(408).addHeader("Retry-After", "0")
            .setBody("""{"error":{"code":"REQUEST_TIMEOUT","message":"Waited"}}"""))
        server.enqueue(stream("event: result\ndata: $MODERN\n\n"))

        val error = assertThrows(AnalyzeApiError.Backend::class.java) {
            runBlocking { client().analyze(request) }
        }

        assertEquals(408, error.statusCode)
        assertEquals(1, server.requestCount)
    }

    @Test fun retryableHttp503DoesNotReplayAnalysisPost() {
        server.enqueue(MockResponse().setResponseCode(503).addHeader("Retry-After", "0")
            .setBody("""{"error":{"code":"UNAVAILABLE","message":"Busy"}}"""))
        server.enqueue(stream("event: result\ndata: $MODERN\n\n"))

        val error = assertThrows(AnalyzeApiError.Backend::class.java) {
            runBlocking { client().analyze(request) }
        }

        assertEquals(503, error.statusCode)
        assertEquals(1, server.requestCount)
    }

    @Test fun redirectDoesNotSendAnalysisToSecondEndpoint() {
        server.enqueue(MockResponse().setResponseCode(307).addHeader("Location", "/other/analyze"))
        server.enqueue(stream("event: result\ndata: $MODERN\n\n"))

        val error = assertThrows(AnalyzeApiError.Http::class.java) {
            runBlocking { client().analyze(request) }
        }

        assertEquals(307, error.statusCode)
        assertEquals(1, server.requestCount)
    }

    @Test fun droppedConnectionDoesNotReconnectAndReplayAnalysisPost() {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.DISCONNECT_AFTER_REQUEST))
        server.enqueue(stream("event: result\ndata: $MODERN\n\n"))

        assertThrows(AnalyzeApiError.Transport::class.java) {
            runBlocking { client().analyze(request) }
        }

        assertEquals(1, server.requestCount)
    }

    @Test fun cancellationClosesUnderlyingHttpCall() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val http = okhttp3.OkHttpClient()
        val job = async(Dispatchers.IO) { client(http).analyze(request) }
        assertNotNull(server.takeRequest(5, TimeUnit.SECONDS))
        job.cancel(CancellationException("leave analysis"))
        withTimeout(5_000) {
            job.join()
            while (http.dispatcher.runningCallsCount() != 0) delay(10)
        }
        try {
            job.await()
            throw AssertionError("Expected cancellation")
        } catch (error: CancellationException) {
            assertEquals("leave analysis", error.message)
        }
        assertEquals(1, server.requestCount)
    }

    private fun client(http: okhttp3.OkHttpClient = okhttp3.OkHttpClient()) =
        AnalyzeStreamingClient(server.url("/v1/"), http)

    private fun stream(body: String) = MockResponse().setResponseCode(200)
        .addHeader("Content-Type", "text/event-stream; charset=utf-8").setBody(body)

    companion object {
        private const val MODERN = """{"transcriptId":"transcript-1","sourceType":"youtube","categories":[{"categoryId":"server-category","title":"영상","keywords":[{"candidateClippingId":"occurrence-1","term":"Codex","brief":"Tool","level1":"One","level2":"Two","level3":"Three","source":{"type":"youtube","ref":"https://example.com?t=46s"},"sources":[{"type":"youtube","ref":"https://example.com?t=46s"},{"type":"youtube","ref":"https://example.com?t=47s"}],"level2CitationIds":["C1"],"level3CitationIds":["C1"],"externalSources":[{"citationId":"C1","title":"Official","url":"https://example.com/official"}]},{"candidateClippingId":"occurrence-2","term":"Codex","brief":"Risk","level1":"One","level2":"Other","level3":"Risk detail","source":{"type":"youtube","ref":"https://example.com?t=312s"},"sources":[{"type":"youtube","ref":"https://example.com?t=312s"}],"level2CitationIds":[],"level3CitationIds":["C2"],"externalSources":[{"citationId":"C2","title":"Research","url":"https://example.com/research"}]}]}],"expiresInSeconds":1800,"videoId":"video-1","llm":{"provider":"openai"}}"""
        private const val LEGACY = """{"transcriptId":"legacy","sourceType":"youtube","categories":[{"title":"Same","keywords":[{"term":"Codex","brief":"First","level1":"One","level2":"Two","level3":"Three","source":{"type":"youtube","ref":"https://example.com?t=1s"}},{"term":"Codex","brief":"Second","level1":"One","level2":"Two","level3":"Three","source":{"type":"youtube","ref":"https://example.com?t=2s"}}]},{"title":"Same","keywords":[{"term":"Codex","brief":"Third","level1":"One","level2":"Two","level3":"Three","source":{"type":"youtube","ref":"https://example.com?t=3s"}}]}],"expiresInSeconds":1800}"""
    }
}
