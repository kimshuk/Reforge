package com.andrewkim.reforge

import android.app.Application
import androidx.lifecycle.ProcessLifecycleOwner
import com.andrewkim.reforge.lifecycle.TrashPurgeObserver

class ReforgeApplication : Application() {
    lateinit var container: AppContainer

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        ProcessLifecycleOwner.get().lifecycle.addObserver(
            TrashPurgeObserver(repository = { container.repository }),
        )
    }
}
