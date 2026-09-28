package com.andrewkim.reforge.network

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runTest
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Before
import org.junit.Test

class YouTubeAvailabilityServiceTest {
    private lateinit var server: MockWebServer
    private val canonical = "https://www.youtube.com/watch?v=dQw4w9WgXcQ".toHttpUrl()

    @Before fun setUp() { server = MockWebServer().also { it.start() } }
    @After fun tearDown() { server.shutdown() }

    @Test fun availableTitleUsesSeparateOEmbedEndpoint() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"title":"Song"}"""))
        val result = YouTubeAvailabilityService(server.url("/")).check(canonical)
        assertEquals(YouTubeAvailability.Available("Song"), result)
        val request = server.takeRequest()
        assertEquals("GET", request.method)
        assertEquals("/oembed", request.requestUrl?.encodedPath)
        assertEquals(canonical.toString(), request.requestUrl?.queryParameter("url"))
        assertEquals("json", request.requestUrl?.queryParameter("format"))
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
}
