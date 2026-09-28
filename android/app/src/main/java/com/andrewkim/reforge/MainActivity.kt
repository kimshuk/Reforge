package com.andrewkim.reforge

import android.content.Intent
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
import com.andrewkim.reforge.sharing.ShareImportState
import com.andrewkim.reforge.sharing.ShareImportViewModel
import com.andrewkim.reforge.ui.theme.ReforgeTheme

class MainActivity : ComponentActivity() {
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
    internal lateinit var appCoordinator: AppCoordinator

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        appCoordinator = AppCoordinator(
            shareImport,
            finishExternalTask = ::finish,
            coldShareLaunch = savedInstanceState?.getBoolean(KEY_COLD_SHARE)
                ?: (intent.action == Intent.ACTION_SEND),
        )
        if (savedInstanceState == null) {
            appCoordinator.acceptShare(intent)
            setIntent(neutralIntent())
        }
        setContent {
            ReforgeTheme {
                val navController = rememberNavController()
                val currentEntry by navController.currentBackStackEntryAsState()
                val shareState by shareImport.state.collectAsStateWithLifecycle()
                ReforgeNavHost(
                    navController = navController,
                    shareState = shareState,
                    onSelectHome = { appCoordinator.selectTab(AppDestination.HOME_GRAPH) },
                    onSelectNotes = { appCoordinator.selectTab(AppDestination.NOTES_GRAPH) },
                    onBackShare = appCoordinator::finishShare,
                    onConfirmRestore = shareImport::confirmRestore,
                    onCancelRestore = {
                        shareImport.cancelRestore()
                        appCoordinator.finishShare()
                    },
                )
                LaunchedEffect(navController, currentEntry) {
                    if (currentEntry == null) return@LaunchedEffect
                    appCoordinator.bind(navController)
                    lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
                        shareImport.state.collect { state ->
                            if (state is ShareImportState.Completed && !state.navigationAcknowledged) {
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
        setIntent(intent)
        appCoordinator.acceptShare(intent)
        setIntent(neutralIntent())
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putBoolean(KEY_COLD_SHARE, appCoordinator.isColdShareLaunch)
        super.onSaveInstanceState(outState)
    }

    private companion object {
        const val KEY_COLD_SHARE = "cold_share_launch"
    }

    private fun neutralIntent() = Intent(Intent.ACTION_MAIN).setClass(this, MainActivity::class.java)
}
