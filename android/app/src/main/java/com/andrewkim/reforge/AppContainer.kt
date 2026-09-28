package com.andrewkim.reforge

import android.content.Context
import com.andrewkim.reforge.config.AppConfig
import com.andrewkim.reforge.network.ShareTitleResolver
import com.andrewkim.reforge.network.YoutubeTranscriptService
import com.andrewkim.reforge.notes.ContentNoteRepository
import com.andrewkim.reforge.notes.ReforgeDatabase
import com.andrewkim.reforge.notes.RoomContentNoteRepository
import com.andrewkim.reforge.sharing.ShareIngesting
import com.andrewkim.reforge.sharing.ShareIngestionCoordinator

class AppContainer(
    context: Context,
    repositoryOverride: ContentNoteRepository? = null,
    ingestorOverride: ShareIngesting? = null,
) {
    private val applicationContext = context.applicationContext
    val repository: ContentNoteRepository by lazy {
        repositoryOverride ?: RoomContentNoteRepository(ReforgeDatabase.open(applicationContext))
    }
    val ingestor: ShareIngesting by lazy {
        ingestorOverride ?: ShareIngestionCoordinator(
            repository,
            YoutubeTranscriptService(
                AppConfig.from(BuildConfig.BACKEND_BASE_URL, BuildConfig.IS_RELEASE).backendBaseUrl,
            ),
            ShareTitleResolver(),
        )
    }
}
