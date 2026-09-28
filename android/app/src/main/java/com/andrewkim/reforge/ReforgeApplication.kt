package com.andrewkim.reforge

import android.app.Application

class ReforgeApplication : Application() {
    lateinit var container: AppContainer

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
