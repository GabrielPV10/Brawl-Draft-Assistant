package com.brawldraft.assistant.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
enum class DraftPhase {
    @SerialName("first_pick") FIRST_PICK,
    @SerialName("mid_picks") MID_PICKS,
    @SerialName("last_pick") LAST_PICK,
}

@Serializable
data class DraftRequestDto(
    @SerialName("map_id") val mapId: Int,
    @SerialName("game_mode") val gameMode: String? = null,
    val phase: DraftPhase,
    val allies: List<Int> = emptyList(),
    val enemies: List<Int> = emptyList(),
    val bans: List<Int> = emptyList(),
    @SerialName("profile_id") val profileId: Int? = null,
    val slot: Int? = null,
    val strategy: String = "balanced",
    @SerialName("top_n") val topN: Int = 3,
)

@Serializable
data class DraftRecommendationDto(
    @SerialName("brawler_id") val brawlerId: Int,
    @SerialName("brawler_name") val brawlerName: String,
    val score: Double,
    val breakdown: Map<String, Double> = emptyMap(),
    val explanation: String? = null,
)

@Serializable
data class DraftResponseDto(
    @SerialName("map_id") val mapId: Int,
    val phase: DraftPhase,
    val recommendations: List<DraftRecommendationDto>,
    @SerialName("computed_in_ms") val computedInMs: Int,
)
