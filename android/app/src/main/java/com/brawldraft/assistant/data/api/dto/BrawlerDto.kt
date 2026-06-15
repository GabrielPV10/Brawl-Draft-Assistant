package com.brawldraft.assistant.data.api.dto

import kotlinx.serialization.Serializable

@Serializable
data class BrawlerDto(
    val id: Int,
    val name: String,
    val slug: String,
)
