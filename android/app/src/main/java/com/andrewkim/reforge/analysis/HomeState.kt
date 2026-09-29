package com.andrewkim.reforge.analysis

import com.andrewkim.reforge.network.VideoUnavailableReason
import com.andrewkim.reforge.sharing.YouTubeVideoIdentity

data class HomeState(
    val url: String = "",
    val title: String = "",
    val isLoading: Boolean = false,
    val loadingStage: String = "",
    val loadingStatusMessage: String = "",
    val errorMessage: String = "",
    val unavailableReason: VideoUnavailableReason? = null,
    val result: AnalyzeResponse? = null,
    val submittedUrl: String = "",
    val expandedCategoryIndex: Int? = null,
    val selection: KeywordSelectionState = KeywordSelectionState(),
    val inputGeneration: Long = 0,
) {
    val identity: YouTubeVideoIdentity?
        get() = YouTubeVideoIdentity.parse(url.trim()).getOrNull()
    val shouldShowTitleArea: Boolean
        get() = result != null || (identity != null && unavailableReason == null)
    val thumbnailUrl: String?
        get() = YouTubeVideoIdentity.parse(if (result != null) submittedUrl else url.trim())
            .getOrNull()?.videoId?.let { "https://img.youtube.com/vi/$it/hqdefault.jpg" }
}
