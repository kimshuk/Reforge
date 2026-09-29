package com.andrewkim.reforge.config

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

data class AppConfig(val backendBaseUrl: HttpUrl) {
    companion object {
        private const val DEBUG_DEFAULT = "http://10.0.2.2:3000"

        fun from(rawValue: String, isRelease: Boolean): AppConfig {
            val value = rawValue.trim()
            require(value.isNotEmpty()) { "Backend base URL is required." }
            require(!value.contains("$(") && !value.contains("${'$'}{")) {
                "Backend base URL contains an unexpanded placeholder."
            }
            require(!isRelease || value != DEBUG_DEFAULT) {
                "Release requires an injected HTTPS backend URL."
            }

            val parsed = value.trimEnd('/').plus('/').toHttpUrlOrNull()
            require(parsed != null && parsed.scheme in setOf("http", "https") &&
                parsed.username.isEmpty() && parsed.password.isEmpty() &&
                parsed.query == null && parsed.fragment == null) {
                "Backend base URL must be a valid HTTP or HTTPS URL."
            }
            require(!isRelease || parsed.scheme == "https") {
                "Release requires an injected HTTPS backend URL."
            }

            return AppConfig(parsed)
        }
    }
}
