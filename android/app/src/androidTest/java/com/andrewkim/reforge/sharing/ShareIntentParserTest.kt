package com.andrewkim.reforge.sharing

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareIntentParserTest {
    @Test fun textShareDelegatesToTextParser() {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "Song https://youtu.be/dQw4w9WgXcQ")
        }
        val result = ShareIntentParser.parse(intent)
        assertTrue(result is SharedTextResult.Valid)
        assertEquals("Song", (result as SharedTextResult.Valid).sharedTitle)
    }

    @Test fun actionMimeAndMissingExtraAreRejected() {
        val valid = Intent(Intent.ACTION_SEND).apply {
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "https://youtu.be/dQw4w9WgXcQ")
        }
        assertSame(SharedTextResult.Invalid, ShareIntentParser.parse(Intent(valid).apply { action = Intent.ACTION_VIEW }))
        assertSame(SharedTextResult.Invalid, ShareIntentParser.parse(Intent(valid).apply { type = "text/html" }))
        assertSame(SharedTextResult.Invalid, ShareIntentParser.parse(Intent(Intent.ACTION_SEND).apply { type = "text/plain" }))
    }
}
