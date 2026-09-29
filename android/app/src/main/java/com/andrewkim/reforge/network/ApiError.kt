package com.andrewkim.reforge.network

import kotlinx.serialization.Serializable

sealed class ApiError(message: String) : Exception(message) {
    data class Backend(val statusCode: Int, val code: String, val backendMessage: String) :
        ApiError(backendMessage)

    data class InvalidResponse(val statusCode: Int) :
        ApiError("Invalid backend response ($statusCode)")
}

@Serializable
internal data class BackendErrorEnvelope(val error: BackendErrorPayload)

@Serializable
internal data class BackendErrorPayload(val code: String, val message: String)
