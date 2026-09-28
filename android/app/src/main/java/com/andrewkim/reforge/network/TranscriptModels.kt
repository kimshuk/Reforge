package com.andrewkim.reforge.network

import kotlinx.serialization.Serializable

@Serializable
data class YoutubeTranscriptRequest(val youtubeUrl: String, val title: String?)

@Serializable
data class YoutubeTranscriptResponse(
    val transcriptId: String,
    val videoId: String,
    val canonicalYoutubeUrl: String,
    val transcriptText: String,
    val languageCode: String?,
    val language: String?,
    val isGenerated: Boolean?,
)
