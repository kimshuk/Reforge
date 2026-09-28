package com.andrewkim.reforge.sharing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class SharedTextParserTest {
    @Test fun proseBeforeUrlBecomesTitle() {
        val result = SharedTextParser.parse("  Favorite song  https://youtu.be/dQw4w9WgXcQ?t=1. ")
        assertTrue(result is SharedTextResult.Valid)
        result as SharedTextResult.Valid
        assertEquals("Favorite song", result.sharedTitle)
        assertEquals("https://youtu.be/dQw4w9WgXcQ?t=1", result.sourceUrl)
    }

    @Test fun sameVideoVariantsAreOneValidInput() {
        val result = SharedTextParser.parse(
            "https://youtu.be/dQw4w9WgXcQ and https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assertTrue(result is SharedTextResult.Valid)
        assertEquals("dQw4w9WgXcQ", (result as SharedTextResult.Valid).identity.videoId)
        assertNull(result.sharedTitle)
    }

    @Test fun distinctVideosAreAmbiguous() {
        assertSame(
            SharedTextResult.Ambiguous,
            SharedTextParser.parse("https://youtu.be/dQw4w9WgXcQ https://youtu.be/aaaaaaaaaaa"),
        )
    }

    @Test fun noValidUrlIsInvalid() {
        assertSame(SharedTextResult.Invalid, SharedTextParser.parse("Please watch this video"))
        assertSame(
            SharedTextResult.Invalid,
            SharedTextParser.parse("https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ"),
        )
    }
}
