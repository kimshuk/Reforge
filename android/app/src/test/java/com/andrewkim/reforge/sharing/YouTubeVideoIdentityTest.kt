package com.andrewkim.reforge.sharing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class YouTubeVideoIdentityTest {
    @Test fun supportedFormsConverge() {
        listOf(
            "https://youtube.com/watch?v=dQw4w9WgXcQ&feature=share",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ#part",
            "http://m.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=4",
            "https://youtube.com/shorts/dQw4w9WgXcQ?si=abc",
        ).forEach { url ->
            val identity = YouTubeVideoIdentity.parse(url).getOrThrow()
            assertEquals("dQw4w9WgXcQ", identity.videoId)
            assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ", identity.canonicalUrl.toString())
            assertEquals("youtube:dQw4w9WgXcQ", identity.sourceKey)
        }
    }

    @Test fun rejectsUnsupportedAndMalformedInputs() {
        listOf(
            "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
            "https://evil.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://user:pass@youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtube.com/embed/dQw4w9WgXcQ",
            "https://youtube.com/watch?v=",
            "https://youtube.com/watch?v=1234567890",
            "https://youtube.com/watch?v=123456789012",
            "https://youtu.be/dQw4w9WgXcQ/extra",
        ).forEach { assertTrue(it, YouTubeVideoIdentity.parse(it).isFailure) }
    }
}
