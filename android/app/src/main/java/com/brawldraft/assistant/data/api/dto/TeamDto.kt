package com.brawldraft.assistant.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class EvaluateRequestDto(
    @SerialName("map_id") val mapId: Int,
    val allies: List<Int>,
    val enemies: List<Int>,
)

@Serializable
data class EvaluateResponseDto(
    @SerialName("win_probability") val winProbability: Double,
    @SerialName("our_avg_score") val ourAvgScore: Double,
    @SerialName("enemy_avg_score") val enemyAvgScore: Double,
)

@Serializable
data class BrawlerProficiencyDto(
    @SerialName("brawler_id") val brawlerId: Int,
    @SerialName("brawler_name") val brawlerName: String,
    val proficiency: Double,
    val trophies: Int,
    @SerialName("power_level") val powerLevel: Int,
    @SerialName("gadgets_unlocked") val gadgetsUnlocked: Int,
    @SerialName("star_powers_unlocked") val starPowersUnlocked: Int,
    @SerialName("recent_winrate") val recentWinrate: Double? = null,
)

@Serializable
data class PlayerProficiencyReportDto(
    @SerialName("player_tag") val playerTag: String,
    val nickname: String? = null,
    val brawlers: List<BrawlerProficiencyDto>,
)

@Serializable
data class TeamProficiencyRequest(
    @SerialName("player_tags") val playerTags: List<String>,
)

@Serializable
data class TeamProficiencyResponse(
    val players: List<PlayerProficiencyReportDto>,
    val cached: Boolean = false,
)
