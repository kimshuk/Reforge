package com.andrewkim.reforge.analysis

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.andrewkim.reforge.openYoutubeUrl

interface HomeEvents {
    fun setUrl(value: String)
    fun setTitle(value: String)
    fun analyze()
    fun toggleCategory(index: Int)
    fun selectKeyword(key: KeywordOccurrence)
    fun advanceKeyword(key: KeywordOccurrence)
    fun removeKeyword(key: KeywordOccurrence)
}

@Composable
fun HomeScreen(
    state: HomeState,
    events: HomeEvents,
) {
    val context = LocalContext.current
    Box(Modifier.fillMaxSize().testTag("home")) {
        Column(Modifier.fillMaxSize()) {
            Column(
                Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                if (state.shouldShowTitleArea) {
                    OutlinedTextField(
                        value = state.title,
                        onValueChange = events::setTitle,
                        label = { Text("Video title") },
                        enabled = !state.isLoading,
                        modifier = Modifier.fillMaxWidth().testTag("home-title"),
                    )
                    state.thumbnailUrl?.let { thumbnail ->
                        AsyncImage(
                            model = thumbnail,
                            contentDescription = state.title,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier.fillMaxWidth().aspectRatio(16f / 9f).testTag("home-thumbnail"),
                        )
                    }
                }
                if (state.errorMessage.isNotEmpty()) Text(state.errorMessage, Modifier.testTag("home-error"))
                val result = state.result
                if (result != null && result.categories.isNotEmpty()) {
                    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState())) {
                        result.categories.forEachIndexed { categoryIndex, category ->
                            FilterChip(
                                selected = state.expandedCategoryIndex == categoryIndex,
                                onClick = { events.toggleCategory(categoryIndex) },
                                label = { Text(category.title) },
                                modifier = Modifier.padding(end = 8.dp).testTag("category-$categoryIndex"),
                            )
                        }
                    }
                    state.expandedCategoryIndex?.let { categoryIndex ->
                        result.categories.getOrNull(categoryIndex)?.let { category ->
                            Column {
                                category.keywords.forEachIndexed { keywordIndex, keyword ->
                                    val key = KeywordOccurrence(categoryIndex, keywordIndex)
                                    FilterChip(
                                        selected = state.selection.isSelected(key),
                                        onClick = { events.selectKeyword(key) },
                                        label = { Text(keyword.term) },
                                        modifier = Modifier.testTag("keyword-$categoryIndex-$keywordIndex"),
                                    )
                                }
                            }
                        }
                    }
                    result.categories.forEachIndexed { categoryIndex, category ->
                        val selected = category.keywords.withIndex().filter {
                            state.selection.isSelected(KeywordOccurrence(categoryIndex, it.index))
                        }
                        if (selected.isNotEmpty()) {
                            Text(category.title)
                            selected.forEach { (keywordIndex, keyword) ->
                                val key = KeywordOccurrence(categoryIndex, keywordIndex)
                                val level = state.selection.level(key)
                                val levelText = when (level) {
                                    2 -> keyword.level2
                                    3 -> keyword.level3
                                    else -> keyword.level1
                                }
                                Column(Modifier.testTag("selected-$categoryIndex-$keywordIndex")) {
                                    Row(verticalAlignment = Alignment.Top) {
                                        Text("- ${keyword.term}: $levelText", Modifier.weight(1f))
                                        TextButton(onClick = { openYoutubeUrl(context, keyword.source.ref) }) {
                                            Text(timestampLabel(keyword.source.ref))
                                        }
                                        if (level < 3) TextButton(onClick = { events.advanceKeyword(key) }) {
                                            Text("expand")
                                        }
                                        TextButton(
                                            onClick = { events.removeKeyword(key) },
                                            modifier = Modifier.semantics { contentDescription = "Remove ${keyword.term}" },
                                        ) { Text("×") }
                                    }
                                    keyword.externalSourcesForLevel(level).forEach { source ->
                                        TextButton(onClick = { openYoutubeUrl(context, source.url) }) {
                                            Text(source.title)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    Spacer(Modifier.padding(bottom = 40.dp))
                } else if (state.url.isBlank()) {
                    Column(Modifier.fillMaxWidth().padding(top = 120.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Add a YouTube link to get started")
                        Text("Paste a video URL in the field below to analyze it.")
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = state.url,
                    onValueChange = events::setUrl,
                    label = { Text("Paste YouTube URL") },
                    enabled = !state.isLoading,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = { events.analyze() }),
                    modifier = Modifier.fillMaxWidth().testTag("home-url"),
                )
            }
        }
        if (state.isLoading) {
            Surface(Modifier.fillMaxSize().testTag("home-progress")) {
                Column(
                    Modifier.fillMaxSize().padding(24.dp),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text("Analyzing Video")
                    Text(state.loadingStatusMessage.ifEmpty { "Preparing analysis." })
                    CircularProgressIndicator(Modifier.padding(16.dp))
                }
            }
        }
    }
}

internal fun timestampLabel(ref: String): String {
    val match = Regex("(?:[?&])t=([^&]+)").find(ref)?.groupValues?.get(1) ?: return "0:00"
    val seconds = match.trimEnd { it.isLetter() }.toIntOrNull() ?: 0
    return "${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}"
}
