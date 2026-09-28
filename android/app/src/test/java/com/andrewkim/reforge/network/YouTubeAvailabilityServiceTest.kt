package com.andrewkim.reforge.network

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.SocketPolicy
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test

class YouTubeAvailabilityServiceTest {
    private lateinit var server: MockWebServer
    private val canonical = "https://www.youtube.com/watch?v=dQw4w9WgXcQ".toHttpUrl()

    @Before fun setUp() { server = MockWebServer().also { it.start() } }
    @After fun tearDown() { server.shutdown() }

    @Test fun availableTitleUsesSeparateOEmbedEndpoint() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody(OEMBED_SUCCESS))
        val result = YouTubeAvailabilityService(server.url("/")).check(canonical)
        assertEquals(YouTubeAvailability.Available("Song"), result)
        val request = server.takeRequest()
        assertEquals("GET", request.method)
        assertEquals("/oembed", request.requestUrl?.encodedPath)
        assertEquals(canonical.toString(), request.requestUrl?.queryParameter("url"))
        assertEquals("json", request.requestUrl?.queryParameter("format"))
    }

    @Test fun shareTitleResolvesStandardOEmbedResponse() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody(OEMBED_SUCCESS))
        val resolver = ShareTitleResolver(YouTubeAvailabilityService(server.url("/")))
        assertEquals("Song", resolver.resolve(canonical))
        assertEquals("/oembed", server.takeRequest().requestUrl?.encodedPath)
    }

    @Test fun unavailableStatusesKeepTypedReasons() = runBlocking {
        mapOf(
            401 to VideoUnavailableReason.PRIVATE_OR_RESTRICTED,
            404 to VideoUnavailableReason.NOT_FOUND_OR_REMOVED,
            429 to VideoUnavailableReason.RATE_LIMITED,
            500 to VideoUnavailableReason.UNKNOWN,
        ).forEach { (status, reason) ->
            server.enqueue(MockResponse().setResponseCode(status))
            assertEquals(
                YouTubeAvailability.Unavailable(reason),
                YouTubeAvailabilityService(server.url("/")).check(canonical),
            )
        }
    }

    @Test fun shareTitleFallsBackOnUnavailableInvalidAndEmptyTitles() = runBlocking {
        val unavailable = ShareTitleResolver(YouTubeAvailabilityChecking { YouTubeAvailability.Unavailable(VideoUnavailableReason.UNKNOWN) })
        assertNull(unavailable.resolve(canonical))
        val invalid = ShareTitleResolver(YouTubeAvailabilityChecking { throw IllegalStateException("network") })
        assertNull(invalid.resolve(canonical))
        val empty = ShareTitleResolver(YouTubeAvailabilityChecking { YouTubeAvailability.Available("   ") })
        assertNull(empty.resolve(canonical))
        val available = ShareTitleResolver(YouTubeAvailabilityChecking { YouTubeAvailability.Available("  Song  ") })
        assertEquals("Song", available.resolve(canonical))
    }

    @Test fun shareTitleTimeoutFallsBack() = runTest {
        val waiting = ShareTitleResolver(
            availability = object : YouTubeAvailabilityChecking {
                override suspend fun check(canonicalUrl: okhttp3.HttpUrl): YouTubeAvailability {
                    return CompletableDeferred<YouTubeAvailability>().await()
                }
            },
            timeoutMillis = 1_500,
        )
        assertNull(waiting.resolve(canonical))
    }

    @Test fun cancellationPropagates() {
        val cancelled = CancellationException("leave screen")
        val resolver = ShareTitleResolver(YouTubeAvailabilityChecking { throw cancelled })
        val actual = assertThrows(CancellationException::class.java) {
            runBlocking { resolver.resolve(canonical) }
        }
        assertEquals(cancelled.message, actual.message)
    }

    @Test fun cancellingInFlightAvailabilityRequestStopsHttpCall() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val client = OkHttpClient()
        val service = YouTubeAvailabilityService(server.url("/"), client)
        val call = async(Dispatchers.IO) { service.check(canonical) }
        assertNotNull(server.takeRequest(5, java.util.concurrent.TimeUnit.SECONDS))
        call.cancel(CancellationException("leave screen"))
        withTimeout(5_000) {
            call.join()
            while (client.dispatcher.runningCallsCount() != 0) delay(10)
        }
        try {
            call.await()
            throw AssertionError("Expected caller cancellation")
        } catch (cancellation: CancellationException) {
            assertEquals("leave screen", cancellation.message)
        }
    }

    @Test fun cancellingInFlightShareTitleRequestPropagatesThroughResolver() = runBlocking {
        server.enqueue(MockResponse().setSocketPolicy(SocketPolicy.NO_RESPONSE))
        val client = OkHttpClient()
        val resolver = ShareTitleResolver(
            YouTubeAvailabilityService(server.url("/"), client), timeoutMillis = 30_000
        )
        val call = async(Dispatchers.IO) { resolver.resolve(canonical) }
        assertNotNull(server.takeRequest(5, java.util.concurrent.TimeUnit.SECONDS))
        call.cancel(CancellationException("leave share"))
        withTimeout(5_000) {
            call.join()
            while (client.dispatcher.runningCallsCount() != 0) delay(10)
        }
        try {
            call.await()
            throw AssertionError("Expected caller cancellation")
        } catch (cancellation: CancellationException) {
            assertEquals("leave share", cancellation.message)
        }
    }

    companion object {
        private const val OEMBED_SUCCESS = """{
          "title":"Song","author_name":"Artist","author_url":"https://www.youtube.com/@artist",
          "type":"video","height":113,"width":200,"version":"1.0",
          "provider_name":"YouTube","provider_url":"https://www.youtube.com/",
          "thumbnail_url":"https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
          "thumbnail_height":360,"thumbnail_width":480
        }"""
    }
}
