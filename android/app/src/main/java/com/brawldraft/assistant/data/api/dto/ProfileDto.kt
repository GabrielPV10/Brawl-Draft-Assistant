package com.brawldraft.assistant.data.api.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ProfileMemberDto(
    val slot: Int,
    @SerialName("player_tag") val playerTag: String,
    val nickname: String? = null,
)

@Serializable
data class ProfileDto(
    val id: Int,
    @SerialName("owner_id") val ownerId: String,
    val name: String,
    val members: List<ProfileMemberDto>,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class ProfileCreateRequest(
    @SerialName("owner_id") val ownerId: String,
    val name: String,
    val members: List<ProfileMemberDto>,
)

@Serializable
data class ProfileUpdateRequest(
    val name: String? = null,
    val members: List<ProfileMemberDto>? = null,
)
