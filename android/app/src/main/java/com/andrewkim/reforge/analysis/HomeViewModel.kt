package com.andrewkim.reforge.analysis

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.andrewkim.reforge.navigation.AnalysisInputSnapshot
import com.andrewkim.reforge.network.YouTubeAvailability
import com.andrewkim.reforge.network.YouTubeAvailabilityChecking
import com.andrewkim.reforge.sharing.YouTubeVideoIdentity
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

fun interface AnalysisRunning {
    suspend fun analyze(request: AnalyzeRequest, onProgress: (AnalyzeProgressUpdate) -> Unit): AnalyzeResponse
}

class HomeViewModel(
    private val availability: YouTubeAvailabilityChecking,
    private val analysis: AnalysisRunning,
) : ViewModel(), HomeEvents {
    private val mutableState = MutableStateFlow(HomeState())
    val state = mutableState.asStateFlow()
    private var availabilityJob: Job? = null
    private var analysisJob: Job? = null
    private var lastAutoFilledUrl = ""
    private var titleRevision = 0L

    override fun setUrl(value: String) {
        val old = mutableState.value
        if (old.url == value) return
        invalidate()
        val trimmed = value.trim()
        val identity = YouTubeVideoIdentity.parse(trimmed).getOrNull()
        mutableState.value = mutableState.value.copy(
            url = value,
            title = if (identity == null || trimmed != lastAutoFilledUrl) "" else old.title,
            isLoading = false,
            loadingStage = "",
            loadingStatusMessage = "",
            errorMessage = "",
            unavailableReason = null,
            result = null,
            submittedUrl = "",
            expandedCategoryIndex = null,
            selection = KeywordSelectionState(),
        )
        if (identity == null || trimmed == lastAutoFilledUrl) return
        val generation = mutableState.value.inputGeneration
        val requestedTitleRevision = titleRevision
        availabilityJob = viewModelScope.launch {
            delay(500)
            try {
                when (val checked = availability.check(identity.canonicalUrl)) {
                    is YouTubeAvailability.Available -> if (isCurrent(generation, value)) {
                        val autoFill = titleRevision == requestedTitleRevision
                        if (autoFill) lastAutoFilledUrl = trimmed
                        mutableState.value = mutableState.value.copy(
                            title = if (autoFill) checked.title else mutableState.value.title,
                            unavailableReason = null, errorMessage = "",
                        )
                    }
                    is YouTubeAvailability.Unavailable -> if (isCurrent(generation, value)) {
                        lastAutoFilledUrl = ""
                        mutableState.value = mutableState.value.copy(
                            title = "", unavailableReason = checked.reason,
                            errorMessage = checked.reason.userMessage,
                        )
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // oEmbed transport and decoding failures do not block backend analysis.
            }
        }
    }

    override fun setTitle(value: String) {
        if (mutableState.value.title == value) return
        titleRevision++
        if (mutableState.value.isLoading) invalidate()
        mutableState.value = mutableState.value.copy(
            title = value,
            isLoading = false,
            loadingStage = "",
            loadingStatusMessage = "",
            errorMessage = "",
        )
    }

    fun applySnapshotAndAnalyze(snapshot: AnalysisInputSnapshot) {
        invalidate()
        titleRevision++
        val generation = mutableState.value.inputGeneration
        lastAutoFilledUrl = snapshot.canonicalUrl
        mutableState.value = HomeState(
            url = snapshot.canonicalUrl,
            title = snapshot.title,
            inputGeneration = generation,
        )
        analyze()
    }

    override fun analyze() {
        val current = mutableState.value
        if (current.isLoading) return
        val title = current.title.trim()
        val url = current.url.trim()
        if (title.isEmpty()) {
            mutableState.value = current.copy(errorMessage = "Please enter a title.")
            return
        }
        if (url.toHttpUrlOrNull() == null) {
            mutableState.value = current.copy(errorMessage = "Please enter a valid YouTube URL.")
            return
        }
        if (YouTubeVideoIdentity.parse(url).isFailure) {
            mutableState.value = current.copy(errorMessage = "URL is not a YouTube link.")
            return
        }
        current.unavailableReason?.let {
            mutableState.value = current.copy(errorMessage = it.userMessage)
            return
        }
        availabilityJob?.cancel()
        val generation = current.inputGeneration
        mutableState.value = current.copy(
            isLoading = true,
            loadingStage = "started",
            loadingStatusMessage = "Starting analysis.",
            errorMessage = "",
            result = null,
            submittedUrl = url,
            expandedCategoryIndex = null,
            selection = KeywordSelectionState(),
        )
        analysisJob = viewModelScope.launch {
            try {
                val result = analysis.analyze(AnalyzeRequest(title = title, youtubeUrl = url)) { progress ->
                    viewModelScope.launch {
                        if (mutableState.value.inputGeneration == generation && mutableState.value.isLoading) {
                            mutableState.value = mutableState.value.copy(
                                loadingStage = progress.stage,
                                loadingStatusMessage = progress.message,
                            )
                        }
                    }
                }
                if (mutableState.value.inputGeneration == generation) {
                    mutableState.value = mutableState.value.copy(
                        result = result, isLoading = false,
                        loadingStage = "", loadingStatusMessage = "",
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                if (mutableState.value.inputGeneration == generation) {
                    mutableState.value = mutableState.value.copy(
                        isLoading = false, loadingStage = "", loadingStatusMessage = "",
                        errorMessage = analysisErrorMessage(error),
                    )
                }
            }
        }
    }

    override fun toggleCategory(index: Int) {
        val current = mutableState.value
        if (current.result?.categories?.getOrNull(index) == null) return
        mutableState.value = current.copy(
            expandedCategoryIndex = if (current.expandedCategoryIndex == index) null else index,
        )
    }

    override fun selectKeyword(key: KeywordOccurrence) {
        val current = mutableState.value
        if (current.result?.categories?.getOrNull(key.categoryIndex)?.keywords?.getOrNull(key.keywordIndex) == null) return
        mutableState.value = current.copy(selection = current.selection.select(key))
    }

    override fun advanceKeyword(key: KeywordOccurrence) {
        val current = mutableState.value
        mutableState.value = current.copy(selection = current.selection.advanceLevel(key))
    }

    override fun removeKeyword(key: KeywordOccurrence) {
        val current = mutableState.value
        mutableState.value = current.copy(selection = current.selection.remove(key))
    }

    private fun invalidate() {
        availabilityJob?.cancel()
        analysisJob?.cancel()
        mutableState.value = mutableState.value.copy(inputGeneration = mutableState.value.inputGeneration + 1)
    }

    private fun isCurrent(generation: Long, url: String): Boolean =
        mutableState.value.inputGeneration == generation && mutableState.value.url == url
}

internal fun analysisErrorMessage(error: Exception): String = when (error) {
    is AnalyzeApiError.Backend -> when (error.code) {
        "YOUTUBE_VIDEO_UNAVAILABLE" -> "This YouTube video is unavailable (private, hidden, or removed)."
        "YOUTUBE_URL_INVALID", "INVALID_YOUTUBE_URL" -> "Invalid YouTube URL. Please check and try again."
        "TRANSCRIPT_UNAVAILABLE" -> "The video is available, but transcript is not available."
        "TRANSCRIPT_PROVIDER_RATE_LIMITED", "OPENAI_QUOTA_OR_RATE_LIMIT" ->
            "Transcript provider is rate-limiting requests. Please try again."
        "TRANSCRIPT_PROVIDER_ERROR", "TRANSCRIPT_FETCH_FAILED" -> "Transcript provider failed. Please try again."
        "PYTHON_DEPENDENCY_MISSING" -> "Backend transcript dependency is missing."
        "PYTHON_RUNTIME_ERROR" -> "Backend could not start the transcript fetcher."
        "TRANSCRIPT_PARSE_FAILED" -> "Backend returned an invalid transcript response."
        "OPENAI_API_KEY_MISSING", "OPENAI_AUTH_ERROR" -> "Backend OpenAI configuration is invalid."
        "OPENAI_BAD_REQUEST", "OPENAI_CONTEXT_LENGTH_EXCEEDED", "OPENAI_INVALID_SOURCE_REF",
        "OPENAI_ANALYZE_FAILED", "OPENAI_ANALYZE_INCOMPLETE", "OPENAI_ANALYZE_INVALID_JSON",
        "OPENAI_ANALYZE_SOURCE_MISMATCH", "OPENAI_ANALYZE_EMPTY" ->
            "Analysis failed on the backend. Please try again."
        else -> error.backendMessage.ifEmpty { "Request failed with code ${error.code}." }
    }
    is AnalyzeApiError.Http -> "Server error (${error.statusCode})."
    is AnalyzeApiError.Transport -> "Analysis connection failed"
    AnalyzeApiError.MissingResult -> "Server finished without returning analysis data."
    is AnalyzeApiError.InvalidResponse -> "Could not decode server response."
    else -> "Invalid response from server."
}
