package com.andrewkim.reforge.notes

import androidx.room.testing.MigrationTestHelper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ReforgeDatabaseMigrationTest {
    @get:Rule val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        ReforgeDatabase::class.java,
    )

    @Test fun version1To2KeepsNotesAndDropsTranscriptId() {
        helper.createDatabase(DB, 1).use { db ->
            db.execSQL(
                """
                INSERT INTO content_notes (
                    id, sourceKey, sourceType, videoId, sourceUrl, canonicalUrl, title,
                    transcriptId, transcriptText, transcriptLanguageCode,
                    transcriptIsGenerated, createdAt, trashedAt
                ) VALUES (
                    'note-1', 'youtube:abc', 'youtube', 'abc', 'https://youtu.be/abc',
                    'https://www.youtube.com/watch?v=abc', 'Title',
                    'transcript-1', 'Saved transcript', 'en', 0, 1000, NULL
                )
                """.trimIndent()
            )
        }

        val db = helper.runMigrationsAndValidate(DB, 2, true)

        db.query("SELECT id, transcriptText FROM content_notes").use { cursor ->
            assertEquals(1, cursor.count)
            cursor.moveToFirst()
            assertEquals("note-1", cursor.getString(0))
            assertEquals("Saved transcript", cursor.getString(1))
        }
        db.query("SELECT * FROM content_notes").use { cursor ->
            assertFalse(cursor.columnNames.contains("transcriptId"))
        }
    }

    private companion object {
        const val DB = "migration-test.db"
    }
}
