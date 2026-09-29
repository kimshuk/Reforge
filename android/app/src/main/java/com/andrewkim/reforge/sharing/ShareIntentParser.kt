package com.andrewkim.reforge.sharing

import android.content.Intent

object ShareIntentParser {
    fun parse(intent: Intent): SharedTextResult {
        if (intent.action != Intent.ACTION_SEND || intent.type != "text/plain") {
            return SharedTextResult.Invalid
        }
        val text = intent.getCharSequenceExtra(Intent.EXTRA_TEXT) ?: return SharedTextResult.Invalid
        return SharedTextParser.parse(text)
    }
}
