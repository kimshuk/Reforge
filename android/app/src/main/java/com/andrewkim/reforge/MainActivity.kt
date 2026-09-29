package com.andrewkim.reforge

import android.content.Intent
import android.content.ActivityNotFoundException
import android.content.Context
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.repeatOnLifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import androidx.navigation.compose.rememberNavController
import androidx.navigation.compose.currentBackStackEntryAsState
import com.andrewkim.reforge.navigation.AppCoordinator
import com.andrewkim.reforge.navigation.AppDestination
import com.andrewkim.reforge.navigation.ReforgeNavHost
import com.andrewkim.reforge.analysis.HomeViewModel
import com.andrewkim.reforge.sharing.ShareImportState
import com.andrewkim.reforge.sharing.ShareImportViewModel
import com.andrewkim.reforge.ui.theme.ReforgeTheme

class MainActivity : ComponentActivity() {
    private var recoverUnfinishedShareOnStart = false
    private val shareImport: ShareImportViewModel by viewModels {
        viewModelFactory {
            initializer {
                ShareImportViewModel(
                    (application as ReforgeApplication).container.ingestor,
                    createSavedStateHandle(),
                )
            }
        }
    }
    private val homeViewModel: HomeViewModel by viewModels {
        viewModelFactory {
            initializer {
                val container = (application as ReforgeApplication).container
                HomeViewModel(container.availability, container.analysis)
            }
        }
    }
    internal lateinit var appCoordinator: AppCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        appCoordinator = AppCoordinator(
            shareImport,
            finishExternalTask = ::finish,
            coldShareLaunch = savedInstanceState?.getBoolean(KEY_COLD_SHARE)
                ?: (intent.action == Intent.ACTION_SEND),
        )
        recoverUnfinishedShareOnStart = savedInstanceState != null
        if (savedInstanceState == null) {
            appCoordinator.acceptShare(intent)
            setIntent(neutralIntent())
        }
        setContent {
            ReforgeTheme {
                val navController = rememberNavController()
                val currentEntry by navController.currentBackStackEntryAsState()
                val shareState by shareImport.state.collectAsStateWithLifecycle()
                val homeState by homeViewModel.state.collectAsStateWithLifecycle()
                val pendingAnalysis by appCoordinator.analysisInput.collectAsStateWithLifecycle()
                ReforgeNavHost(
                    navController = navController,
                    shareState = shareState,
                    homeState = homeState,
                    homeEvents = homeViewModel,
                    repository = (application as ReforgeApplication).container.repository,
                    onSelectHome = { appCoordinator.selectTab(AppDestination.HOME_GRAPH) },
                    onSelectNotes = { appCoordinator.selectTab(AppDestination.NOTES_GRAPH) },
                    onAnalyzeNote = appCoordinator::openHomeForAnalysis,
                    onOpenYoutube = { url -> openYoutubeUrl(this, url) },
                    onBackShare = ::finishShare,
                    onConfirmRestore = shareImport::confirmRestore,
                    onCancelRestore = ::finishShare,
                )
                LaunchedEffect(pendingAnalysis) {
                    pendingAnalysis?.let { snapshot ->
                        homeViewModel.applySnapshotAndAnalyze(snapshot)
                        appCoordinator.acknowledgeAnalysisInput(snapshot)
                    }
                }
                LaunchedEffect(navController, currentEntry) {
                    if (currentEntry == null) return@LaunchedEffect
                    appCoordinator.bind(navController)
                    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                        shareImport.state.collect { state ->
                            if (recoverUnfinishedShareOnStart &&
                                currentEntry?.destination?.route == AppDestination.SHARE_IMPORT &&
                                (state is ShareImportState.Idle || state is ShareImportState.Finished ||
                                    (state is ShareImportState.Completed && state.navigationAcknowledged))
                            ) {
                                finishShare()
                            } else if (state is ShareImportState.Completed && !state.navigationAcknowledged) {
                                recoverUnfinishedShareOnStart = false
                                appCoordinator.completeShare(state)
                            }
                        }
                    }
                }
                DisposableEffect(navController) {
                    onDispose { appCoordinator.unbind(navController) }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        recoverUnfinishedShareOnStart = false
        setIntent(intent)
        appCoordinator.acceptShare(intent)
        setIntent(neutralIntent())
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean(KEY_COLD_SHARE, appCoordinator.isColdShareLaunch)
        super.onSaveInstanceState(outState)
    }

    private fun finishShare() {
        // Disarm recovery before cancelImport publishes Finished to the collector.
        recoverUnfinishedShareOnStart = false
        appCoordinator.finishShare()
    }

    private companion object {
        const val KEY_COLD_SHARE = "cold_share_launch"
    }

    private fun neutralIntent() = Intent(Intent.ACTION_MAIN).setClass(this, MainActivity::class.java)
}

internal fun openYoutubeUrl(context: Context, url: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (_: ActivityNotFoundException) {
        // Keep the current screen when no application can handle the URL.
    }
}
