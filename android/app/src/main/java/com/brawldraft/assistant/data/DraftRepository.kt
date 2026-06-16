package com.brawldraft.assistant.data

import com.brawldraft.assistant.data.api.ApiClient
import com.brawldraft.assistant.data.api.ApiService
import com.brawldraft.assistant.data.api.dto.BrawlerDto
import com.brawldraft.assistant.data.api.dto.DraftRequestDto
import com.brawldraft.assistant.data.api.dto.DraftResponseDto
import com.brawldraft.assistant.data.api.dto.EvaluateRequestDto
import com.brawldraft.assistant.data.api.dto.EvaluateResponseDto
import com.brawldraft.assistant.data.api.dto.MapDto
import com.brawldraft.assistant.data.api.dto.ModeMapsDto

/**
 * Repositorio único para draft. Por ahora sólo proxy al backend; en Fase 2/3
 * se puede agregar cache local + fallback a /recommend/dummy si la red falla.
 */
class DraftRepository(
    private val api: ApiService = ApiClient.service,
) {

    suspend fun recommend(req: DraftRequestDto): Result<DraftResponseDto> = runCatching {
        api.recommend(req)
    }

    suspend fun recommendDummy(): Result<DraftResponseDto> = runCatching {
        api.recommendDummy()
    }

    suspend fun searchBrawler(query: String): Result<List<BrawlerDto>> = runCatching {
        api.searchBrawlers(query)
    }

    suspend fun searchMap(query: String): Result<List<MapDto>> = runCatching {
        api.searchMaps(query)
    }

    suspend fun mapsCatalog(): Result<List<ModeMapsDto>> = runCatching {
        api.mapsCatalog()
    }

    suspend fun evaluateTeam(req: EvaluateRequestDto): Result<EvaluateResponseDto> = runCatching {
        api.evaluateTeam(req)
    }

    suspend fun health(): Result<Boolean> = runCatching {
        api.health()["status"] == "ok"
    }
}
