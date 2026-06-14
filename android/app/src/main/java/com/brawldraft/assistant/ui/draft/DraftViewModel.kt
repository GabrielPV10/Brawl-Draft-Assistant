package com.brawldraft.assistant.ui.draft

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.brawldraft.assistant.data.DraftRepository
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto
import com.brawldraft.assistant.data.api.dto.DraftRequestDto
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DraftUiState(
    val mapIdInput: String = "15040002",
    val phase: DraftPhase = DraftPhase.FIRST_PICK,
    val alliesInput: String = "",
    val enemiesInput: String = "",
    val bansInput: String = "",
    val loading: Boolean = false,
    val recommendations: List<DraftRecommendationDto> = emptyList(),
    val computedInMs: Int = 0,
    val error: String? = null,
)

class DraftViewModel(
    private val repo: DraftRepository = DraftRepository(),
) : ViewModel() {

    private val _state = MutableStateFlow(DraftUiState())
    val state: StateFlow<DraftUiState> = _state.asStateFlow()

    fun setMapId(text: String) = _state.update { it.copy(mapIdInput = text) }
    fun setPhase(phase: DraftPhase) = _state.update { it.copy(phase = phase) }
    fun setAllies(text: String) = _state.update { it.copy(alliesInput = text) }
    fun setEnemies(text: String) = _state.update { it.copy(enemiesInput = text) }
    fun setBans(text: String) = _state.update { it.copy(bansInput = text) }

    fun fetchDummy() {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.recommendDummy().fold(
                onSuccess = { resp ->
                    _state.update {
                        it.copy(
                            loading = false,
                            recommendations = resp.recommendations,
                            computedInMs = resp.computedInMs,
                        )
                    }
                },
                onFailure = { e -> _state.update { it.copy(loading = false, error = e.message) } },
            )
        }
    }

    fun recommend() {
        val current = _state.value
        val mapId = current.mapIdInput.toIntOrNull()
        if (mapId == null) {
            _state.update { it.copy(error = "map_id inválido") }
            return
        }
        val req = DraftRequestDto(
            mapId = mapId,
            phase = current.phase,
            allies = parseIds(current.alliesInput),
            enemies = parseIds(current.enemiesInput),
            bans = parseIds(current.bansInput),
        )
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.recommend(req).fold(
                onSuccess = { resp ->
                    _state.update {
                        it.copy(
                            loading = false,
                            recommendations = resp.recommendations,
                            computedInMs = resp.computedInMs,
                        )
                    }
                },
                onFailure = { e -> _state.update { it.copy(loading = false, error = e.message) } },
            )
        }
    }

    private fun parseIds(input: String): List<Int> =
        input.split(',', ' ', ';')
            .mapNotNull { it.trim().toIntOrNull() }
}
