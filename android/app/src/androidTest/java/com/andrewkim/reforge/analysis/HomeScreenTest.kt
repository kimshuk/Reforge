package com.andrewkim.reforge.analysis

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performImeAction
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class HomeScreenTest {
    @get:Rule val compose = createComposeRule()

    @Test fun emptyPromptTitleAndProgressStates() {
        var state by mutableStateOf(HomeState())
        compose.setContent { HomeScreen(state, events({ state }, { state = it })) }
        compose.onNodeWithText("Add a YouTube link to get started").assertExists()
        compose.onNodeWithTag("home-title").assertDoesNotExist()
        compose.runOnIdle { state = state.copy(url = URL, title = "Saved") }
        compose.onNodeWithTag("home-title").assertExists()
        compose.onNodeWithTag("home-thumbnail").assertExists()
        compose.runOnIdle { state = state.copy(isLoading = true, loadingStatusMessage = "Fetching") }
        compose.onNodeWithTag("home-progress").assertExists()
        compose.onNodeWithText("Fetching").assertExists()
    }

    @Test fun categorySelectionLevelCitationsAndDuplicateOccurrences() {
        var state by mutableStateOf(HomeState(url = URL, title = "Title", submittedUrl = URL, result = result()))
        compose.setContent { HomeScreen(state, events({ state }, { state = it })) }
        compose.onNodeWithTag("category-0").performClick()
        compose.onNodeWithTag("keyword-0-0").performClick()
        compose.onNodeWithTag("selected-0-0").assertExists()
        compose.onNodeWithText("Level 1", substring = true).assertExists()
        compose.onNodeWithText("expand").performClick()
        compose.onNodeWithText("Level 2", substring = true).assertExists()
        compose.onNodeWithText("Citation two").assertExists()
        compose.onNodeWithText("expand").performClick()
        compose.onNodeWithText("Level 3", substring = true).assertExists()
        compose.onNodeWithText("Citation three").assertExists()
        compose.onNodeWithText("expand").assertDoesNotExist()
        compose.onNodeWithText("1:01").assertExists()
        compose.onNodeWithTag("category-1").performClick()
        compose.onNodeWithTag("keyword-1-0").performClick()
        compose.runOnIdle {
            assertEquals(3, state.selection.level(KeywordOccurrence(0, 0)))
            assertEquals(1, state.selection.level(KeywordOccurrence(1, 0)))
        }
    }

    @Test fun urlGoInvokesAnalyze() {
        var state by mutableStateOf(HomeState(url = URL, title = "Title"))
        var analyzes = 0
        compose.setContent { HomeScreen(state, events({ state }, { state = it }) { analyzes++ }) }
        compose.onNodeWithTag("home-url").performImeAction()
        compose.runOnIdle { assertEquals(1, analyzes) }
    }

    private fun events(
        currentState: () -> HomeState,
        update: (HomeState) -> Unit,
        onAnalyze: () -> Unit = {},
    ) = object : HomeEvents {
        override fun setUrl(value: String) = update(current().copy(url = value))
        override fun setTitle(value: String) = update(current().copy(title = value))
        override fun analyze() = onAnalyze()
        override fun toggleCategory(index: Int) = update(current().copy(
            expandedCategoryIndex = if (current().expandedCategoryIndex == index) null else index))
        override fun selectKeyword(key: KeywordOccurrence) = update(current().copy(
            selection = current().selection.select(key)))
        override fun advanceKeyword(key: KeywordOccurrence) = update(current().copy(
            selection = current().selection.advanceLevel(key)))
        override fun removeKeyword(key: KeywordOccurrence) = update(current().copy(
            selection = current().selection.remove(key)))
        private fun current(): HomeState = currentState()
    }

    private fun result(): AnalyzeResponse {
        val keyword = AnalyzeKeyword("same", "same", "Term", "Brief", "Level 1", "Level 2", "Level 3",
            AnalyzeSource("youtube", "$URL&t=61"), emptyList(), listOf("two"), listOf("three"),
            listOf(AnalyzeExternalSource("two", "Citation two", "https://example.com/2"),
                AnalyzeExternalSource("three", "Citation three", "https://example.com/3")))
        return AnalyzeResponse("transcript", "youtube", listOf(
            AnalyzeCategory("same", "same", "First", listOf(keyword)),
            AnalyzeCategory("same", "same", "Second", listOf(keyword)),
        ), 60, "dQw4w9WgXcQ")
    }

    private companion object { const val URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }
}
