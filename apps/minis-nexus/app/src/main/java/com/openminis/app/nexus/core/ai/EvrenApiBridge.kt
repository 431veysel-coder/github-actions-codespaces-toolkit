package com.openminis.app.nexus.core.ai

import android.util.Log

class EvrenApiBridge(private val apiKey: String? = null) {

    companion object {
        private const val TAG = "MinisEvrenBridge"
        private const val BASE_URL = "https://api.ssyz.org.tr/api/v1"
    }

    fun listModels(): String {
        Log.i(TAG, "Calling EVREN API list_models at $BASE_URL/models")
        return "EVREN Model List Response"
    }

    fun chatCompletion(model: String, prompt: String): String {
        Log.i(TAG, "Sending chat completion request to EVREN model: $model")
        return "EVREN Chat Completion Response"
    }
}
