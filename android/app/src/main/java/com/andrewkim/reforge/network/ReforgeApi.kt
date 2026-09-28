package com.andrewkim.reforge.network

import okhttp3.RequestBody
import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.POST

interface ReforgeApi {
    @POST("youtube/transcript")
    suspend fun transcript(@Body body: RequestBody): Response<ResponseBody>
}
