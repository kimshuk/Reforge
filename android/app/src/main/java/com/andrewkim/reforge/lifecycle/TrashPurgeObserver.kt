package com.andrewkim.reforge.lifecycle

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import com.andrewkim.reforge.notes.ContentNoteRepository
import java.time.Clock
import java.time.Duration
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class TrashPurgeObserver(
    private val repository: () -> ContentNoteRepository,
    private val clock: Clock = Clock.systemUTC(),
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO),
) : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner) {
        scope.launch {
            try {
                repository().purgeExpired(clock.instant().minus(Duration.ofDays(30)))
            } catch (error: CancellationException) {
                throw error
            } catch (_: Exception) {
                // A later foreground or Trash entry retries without interrupting navigation.
            }
        }
    }
}
