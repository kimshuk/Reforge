package com.andrewkim.reforge.analysis

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class AnalyzeRequest(
    val type: String = "youtube",
    val title: String,
    val youtubeUrl: String,
)

data class AnalyzeResponse(
    val transcriptId: String,
    val sourceType: String,
    val categories: List<AnalyzeCategory>,
    val expiresInSeconds: Int,
    val videoId: String?,
)

data class AnalyzeCategory(
    val categoryId: String?,
    val id: String,
    val title: String,
    val keywords: List<AnalyzeKeyword>,
)

data class AnalyzeKeyword(
    val candidateClippingId: String?,
    val id: String,
    val term: String,
    val brief: String,
    val level1: String,
    val level2: String,
    val level3: String,
    val source: AnalyzeSource,
    val sources: List<AnalyzeSource>,
    val level2CitationIds: List<String>,
    val level3CitationIds: List<String>,
    val externalSources: List<AnalyzeExternalSource>,
) {
    fun externalSourcesForLevel(level: Int): List<AnalyzeExternalSource> {
        val ids = when (level) {
            2 -> level2CitationIds
            3 -> level3CitationIds
            else -> emptyList()
        }.toSet()
        return externalSources.filter { it.citationId in ids }
    }
}

@Serializable
data class AnalyzeSource(val type: String, val ref: String)

@Serializable
data class AnalyzeExternalSource(val citationId: String, val title: String, val url: String)

@Serializable
private data class AnalyzeResponsePayload(
    val transcriptId: String,
    val sourceType: String,
    val categories: List<AnalyzeCategoryPayload>,
    val expiresInSeconds: Int,
    val videoId: String? = null,
) {
    fun resolveIdentity(): AnalyzeResponse = AnalyzeResponse(
        transcriptId = transcriptId,
        sourceType = sourceType,
        categories = categories.mapIndexed { categoryIndex, category ->
            val categoryIdentity = category.categoryId ?: "$transcriptId:category:$categoryIndex"
            AnalyzeCategory(
                categoryId = category.categoryId,
                id = categoryIdentity,
                title = category.title,
                keywords = category.keywords.mapIndexed { keywordIndex, keyword ->
                    AnalyzeKeyword(
                        candidateClippingId = keyword.candidateClippingId,
                        id = keyword.candidateClippingId ?: "$categoryIdentity:keyword:$keywordIndex",
                        term = keyword.term,
                        brief = keyword.brief,
                        level1 = keyword.level1,
                        level2 = keyword.level2,
                        level3 = keyword.level3,
                        source = keyword.source,
                        sources = keyword.sources ?: listOf(keyword.source),
                        level2CitationIds = keyword.level2CitationIds,
                        level3CitationIds = keyword.level3CitationIds,
                        externalSources = keyword.externalSources,
                    )
                },
            )
        },
        expiresInSeconds = expiresInSeconds,
        videoId = videoId,
    )
}

@Serializable
private data class AnalyzeCategoryPayload(
    val categoryId: String? = null,
    val title: String,
    val keywords: List<AnalyzeKeywordPayload>,
)

@Serializable
private data class AnalyzeKeywordPayload(
    val candidateClippingId: String? = null,
    val term: String,
    val brief: String,
    val level1: String,
    val level2: String,
    val level3: String,
    val source: AnalyzeSource,
    val sources: List<AnalyzeSource>? = null,
    val level2CitationIds: List<String> = emptyList(),
    val level3CitationIds: List<String> = emptyList(),
    val externalSources: List<AnalyzeExternalSource> = emptyList(),
)

internal fun Json.decodeAnalyzeResponse(payload: String): AnalyzeResponse =
    decodeFromString<AnalyzeResponsePayload>(payload).resolveIdentity()
