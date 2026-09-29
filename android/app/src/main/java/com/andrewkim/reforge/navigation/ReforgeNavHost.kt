package com.andrewkim.reforge.navigation

import androidx.activity.compose.BackHandler
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
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
import com.andrewkim.reforge.analysis.HomeEvents
import com.andrewkim.reforge.analysis.HomeScreen
import com.andrewkim.reforge.analysis.HomeState
import com.andrewkim.reforge.sharing.ShareImportState
import com.andrewkim.reforge.notes.ContentNoteRepository
import com.andrewkim.reforge.notes.NoteDetailScreen
import com.andrewkim.reforge.notes.NoteDetailViewModel
import com.andrewkim.reforge.notes.NotesListScreen
import com.andrewkim.reforge.notes.NotesListViewModel
import com.andrewkim.reforge.notes.TrashScreen
import com.andrewkim.reforge.notes.TrashViewModel

@Composable
fun ReforgeNavHost(
    navController: NavHostController,
    shareState: ShareImportState,
    homeState: HomeState,
    homeEvents: HomeEvents,
    repository: ContentNoteRepository,
    onSelectHome: () -> Unit,
    onSelectNotes: () -> Unit,
    onAnalyzeNote: (AnalysisInputSnapshot) -> Unit,
    onOpenYoutube: (String) -> Unit,
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
                    HomeScreen(homeState, homeEvents)
                }
            }
            navigation(startDestination = AppDestination.NOTES, route = AppDestination.NOTES_GRAPH) {
                composable(AppDestination.NOTES) {
                    val notesViewModel: NotesListViewModel = viewModel(factory = viewModelFactory {
                        initializer { NotesListViewModel(repository) }
                    })
                    val notes by notesViewModel.notes.collectAsStateWithLifecycle()
                    NotesListScreen(
                        notes = notes,
                        onOpenNote = { navController.navigate(AppDestination.note(it)) },
                        onOpenTrash = { navController.navigate(AppDestination.TRASH) },
                        onMoveToTrash = notesViewModel::moveToTrash,
                    )
                }
                composable(AppDestination.NOTE_PATTERN) { entry ->
                    val noteId = requireNotNull(entry.arguments?.getString("noteId"))
                    val detailViewModel: NoteDetailViewModel = viewModel(factory = viewModelFactory {
                        initializer { NoteDetailViewModel(repository, noteId) }
                    })
                    val detailState by detailViewModel.state.collectAsStateWithLifecycle()
                    NoteDetailScreen(
                        state = detailState,
                        onMissing = { navController.popBackStack(AppDestination.NOTES, false) },
                        onOpenYoutube = onOpenYoutube,
                        onAnalyze = onAnalyzeNote,
                        onMoveToTrash = detailViewModel::moveToTrash,
                    )
                }
                composable(AppDestination.TRASH) {
                    val trashViewModel: TrashViewModel = viewModel(factory = viewModelFactory {
                        initializer { TrashViewModel(repository) }
                    })
                    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { trashViewModel.onResume() }
                    val trashNotes by trashViewModel.notes.collectAsStateWithLifecycle()
                    TrashScreen(
                        notes = trashNotes,
                        onRestore = trashViewModel::restore,
                        onDelete = trashViewModel::deletePermanently,
                    )
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
