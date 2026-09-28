package com.andrewkim.reforge.navigation

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.navigation.NavHostController
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.navigation
import com.andrewkim.reforge.sharing.ShareImportScreen
import com.andrewkim.reforge.sharing.ShareImportState

@Composable
fun ReforgeNavHost(
    navController: NavHostController,
    shareState: ShareImportState,
    onSelectHome: () -> Unit,
    onSelectNotes: () -> Unit,
    onBackShare: () -> Unit,
    onConfirmRestore: () -> Unit,
    onCancelRestore: () -> Unit,
) {
    val currentEntry by navController.currentBackStackEntryAsState()
    val route = currentEntry?.destination?.route
    val inShare = route == AppDestination.SHARE_IMPORT
    val inNotes = currentEntry?.destination?.hierarchy?.any {
        it.route == AppDestination.NOTES_GRAPH
    } == true
    Scaffold(bottomBar = {
        if (!inShare) NavigationBar {
            NavigationBarItem(
                selected = !inNotes,
                onClick = onSelectHome,
                label = { Text("Home") },
                icon = {},
            )
            NavigationBarItem(
                selected = inNotes,
                onClick = onSelectNotes,
                label = { Text("My Notes") },
                icon = {},
            )
        }
    }) { padding ->
        NavHost(
            navController = navController,
            startDestination = AppDestination.HOME_GRAPH,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            navigation(startDestination = AppDestination.HOME, route = AppDestination.HOME_GRAPH) {
                composable(AppDestination.HOME) {
                    Surface(modifier = Modifier.fillMaxSize().testTag("home")) { Text("Home") }
                }
            }
            navigation(startDestination = AppDestination.NOTES, route = AppDestination.NOTES_GRAPH) {
                composable(AppDestination.NOTES) {
                    Surface(modifier = Modifier.fillMaxSize().testTag("my-notes")) { Text("My Notes") }
                }
                composable(AppDestination.NOTE_PATTERN) {
                    Surface(modifier = Modifier.fillMaxSize().testTag("note-detail")) {}
                }
                composable(AppDestination.TRASH) {
                    Surface(modifier = Modifier.fillMaxSize().testTag("trash")) {}
                }
            }
            composable(AppDestination.SHARE_IMPORT) {
                BackHandler(onBack = onBackShare)
                ShareImportScreen(
                    state = shareState,
                    onBack = onBackShare,
                    onCancelRestore = onCancelRestore,
                    onConfirmRestore = onConfirmRestore,
                )
            }
        }
    }
}
