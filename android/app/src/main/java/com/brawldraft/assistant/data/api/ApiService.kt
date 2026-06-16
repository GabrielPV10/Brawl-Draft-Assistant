package com.brawldraft.assistant.data.api

import com.brawldraft.assistant.data.api.dto.BrawlerDto
import com.brawldraft.assistant.data.api.dto.DraftRequestDto
import com.brawldraft.assistant.data.api.dto.MapDto
import com.brawldraft.assistant.data.api.dto.ModeMapsDto
import com.brawldraft.assistant.data.api.dto.DraftResponseDto
import com.brawldraft.assistant.data.api.dto.ProfileCreateRequest
import com.brawldraft.assistant.data.api.dto.ProfileDto
import com.brawldraft.assistant.data.api.dto.ProfileUpdateRequest
import com.brawldraft.assistant.data.api.dto.EvaluateRequestDto
import com.brawldraft.assistant.data.api.dto.EvaluateResponseDto
import com.brawldraft.assistant.data.api.dto.TeamProficiencyRequest
import com.brawldraft.assistant.data.api.dto.TeamProficiencyResponse
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

interface ApiService {

    @GET("/health")
    suspend fun health(): Map<String, String>

    @GET("/brawlers/search")
    suspend fun searchBrawlers(@Query("q") query: String): List<BrawlerDto>

    @GET("/maps/search")
    suspend fun searchMaps(@Query("q") query: String): List<MapDto>

    @GET("/maps/catalog")
    suspend fun mapsCatalog(): List<ModeMapsDto>

    @POST("/recommend")
    suspend fun recommend(@Body req: DraftRequestDto): DraftResponseDto

    @GET("/recommend/dummy")
    suspend fun recommendDummy(): DraftResponseDto

    @POST("/team/evaluate")
    suspend fun evaluateTeam(@Body req: EvaluateRequestDto): EvaluateResponseDto

    @POST("/team/proficiency")
    suspend fun teamProficiency(@Body req: TeamProficiencyRequest): TeamProficiencyResponse

    @GET("/profiles")
    suspend fun listProfiles(@Query("owner_id") ownerId: String): List<ProfileDto>

    @POST("/profiles")
    suspend fun createProfile(@Body req: ProfileCreateRequest): ProfileDto

    @PATCH("/profiles/{id}")
    suspend fun updateProfile(@Path("id") id: Int, @Body req: ProfileUpdateRequest): ProfileDto

    @DELETE("/profiles/{id}")
    suspend fun deleteProfile(@Path("id") id: Int)
}
