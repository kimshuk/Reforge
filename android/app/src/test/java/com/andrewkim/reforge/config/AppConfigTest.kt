package com.andrewkim.reforge.config

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class AppConfigTest {
    @Test fun debugDefault() {
        assertEquals("http://10.0.2.2:3000/", AppConfig.from("http://10.0.2.2:3000", false).backendBaseUrl.toString())
    }

    @Test fun debugInjectedLanUrl() {
        assertEquals("http://192.168.1.12:3000/", AppConfig.from(" http://192.168.1.12:3000/// ", false).backendBaseUrl.toString())
    }

    @Test fun invalidValues() {
        listOf("", "  ", "$(REFORGE_BACKEND_BASE_URL)", "${'$'}{REFORGE_BACKEND_BASE_URL}", "not a url", "https://").forEach {
            assertThrows(IllegalArgumentException::class.java) { AppConfig.from(it, false) }
        }
    }

    @Test fun releaseRequiresInjectedHttps() {
        assertEquals("https://api.example.invalid/", AppConfig.from("https://api.example.invalid", true).backendBaseUrl.toString())
        listOf(
            "", "http://10.0.2.2:3000", "http://api.example.invalid",
            "https://example.invalid:0", "https://example.invalid:99999", "https://example.invalid/$(BACKEND_PATH)"
        ).forEach {
            assertThrows(IllegalArgumentException::class.java) { AppConfig.from(it, true) }
        }
    }
}
