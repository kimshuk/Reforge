package com.andrewkim.reforge.navigation

import android.content.Intent
import androidx.navigation.NavHostController
import androidx.navigation.NavGraph.Companion.findStartDestination
import com.andrewkim.reforge.sharing.ShareImportState
import com.andrewkim.reforge.sharing.ShareImportViewModel
import com.andrewkim.reforge.sharing.ShareIntentParser
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

class AppCoordinator(
    private val shareImport: ShareImportViewModel,
    private val finishExternalTask: () -> Unit,
    private var coldShareLaunch: Boolean = false,
) {
    private var navController: NavHostController? = null
    private var pendingDestination: String? = null
    val isColdShareLaunch: Boolean get() = coldShareLaunch
    private val mutableAnalysisInput = MutableStateFlow<AnalysisInputSnapshot?>(null)
    val analysisInput = mutableAnalysisInput.asStateFlow()
    internal fun currentRoute(): String? = navController?.currentBackStackEntry?.destination?.route
    internal fun currentNoteId(): String? = navController?.currentBackStackEntry?.arguments?.getString("noteId")

    fun bind(navController: NavHostController) {
        this.navController = navController
        pendingDestination?.let { destination ->
            pendingDestination = null
            navigate(destination)
        }
    }

    fun unbind(navController: NavHostController) {
        if (this.navController === navController) this.navController = null
    }

    fun acceptShare(intent: Intent) {
        if (intent.action == Intent.ACTION_SEND) {
            shareImport.accept(ShareIntentParser.parse(intent))
            navigate(AppDestination.SHARE_IMPORT)
        } else {
            shareImport.abandonForGeneralLaunch()
            if (navController?.currentBackStackEntry?.destination?.route == AppDestination.SHARE_IMPORT) {
                navController?.popBackStack()
            }
            coldShareLaunch = false
            navigate(AppDestination.HOME_GRAPH)
        }
    }

    fun openNote(noteId: String) {
        selectTab(AppDestination.NOTES_GRAPH)
        navController?.navigate(AppDestination.note(noteId))
    }

    fun openHomeForAnalysis(snapshot: AnalysisInputSnapshot) {
        mutableAnalysisInput.value = snapshot
        selectTab(AppDestination.HOME_GRAPH)
    }

    fun acknowledgeAnalysisInput(snapshot: AnalysisInputSnapshot) {
        if (mutableAnalysisInput.value === snapshot) mutableAnalysisInput.value = null
    }

    fun selectTab(route: String) {
        val nav = navController ?: run { pendingDestination = route; return }
        nav.navigate(route) {
            popUpTo(nav.graph.findStartDestination().id) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun completeShare(completed: ShareImportState.Completed) {
        val current = shareImport.state.value as? ShareImportState.Completed ?: return
        if (current.generation != completed.generation || current.noteId != completed.noteId ||
            current.navigationAcknowledged
        ) return
        val nav = navController ?: return
        if (nav.currentBackStackEntry?.destination?.route == AppDestination.SHARE_IMPORT) {
            nav.popBackStack()
        }
        selectTab(AppDestination.NOTES_GRAPH)
        nav.navigate(AppDestination.note(current.noteId)) {
            popUpTo(AppDestination.NOTES) { inclusive = false }
            launchSingleTop = true
        }
        shareImport.acknowledgeDetailOpened(current.generation, current.noteId)
        coldShareLaunch = false
    }

    fun finishShare() {
        shareImport.cancelImport()
        val nav = navController
        if (coldShareLaunch) {
            finishExternalTask()
        } else if (nav?.popBackStack() != true) {
            finishExternalTask()
        }
    }

    private fun navigate(route: String) {
        val nav = navController ?: run { pendingDestination = route; return }
        if (route == AppDestination.HOME_GRAPH) {
            selectTab(route)
        } else {
            nav.navigate(route) { launchSingleTop = true }
        }
    }
}
