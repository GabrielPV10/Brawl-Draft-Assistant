package com.brawldraft.assistant.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class MapDto(
    val id: Int,
    val name: String,
    val slug: String,
    val game_mode: String,
)

@Serializable
data class ModeMapsDto(
    val mode: String,
    val maps: List<MapDto>,
)
