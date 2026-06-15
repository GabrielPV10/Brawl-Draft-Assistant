package com.brawldraft.assistant.ui.draft

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.brawldraft.assistant.data.DraftRepository
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto
import com.brawldraft.assistant.data.api.dto.DraftRequestDto
import com.brawldraft.assistant.data.api.dto.MapDto
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class DraftUiState(
    val mapQuery: String = "Hard Rock Mine",
    val mapSuggestions: List<MapDto> = emptyList(),
    val selectedMap: MapDto? = MapDto(id = 15000007, name = "Hard Rock Mine", slug = "hard-rock-mine", game_mode = "Gem Grab"),
    val mapDropdownExpanded: Boolean = false,
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

    private var searchJob: Job? = null

    fun setMapQuery(text: String) {
        _state.update { it.copy(mapQuery = text, selectedMap = null, mapDropdownExpanded = true) }
        searchJob?.cancel()
        if (text.length < 2) {
            _state.update { it.copy(mapSuggestions = emptyList()) }
            return
        }
        searchJob = viewModelScope.launch {
            delay(300)
            repo.searchMap(text).onSuccess { results ->
                _state.update { it.copy(mapSuggestions = results, mapDropdownExpanded = results.isNotEmpty()) }
            }
        }
    }

    fun selectMap(map: MapDto) {
        _state.update {
            it.copy(
                selectedMap = map,
                mapQuery = "${map.name} · ${map.game_mode}",
                mapSuggestions = emptyList(),
                mapDropdownExpanded = false,
            )
        }
    }

    fun dismissMapDropdown() = _state.update { it.copy(mapDropdownExpanded = false) }

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
        val mapId = current.selectedMap?.id
        if (mapId == null) {
            _state.update { it.copy(error = "Selecciona un mapa del listado") }
            return
        }
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            try {
                val (allies, enemies, bans) = listOf(
                    async { resolveIds(current.alliesInput) },
                    async { resolveIds(current.enemiesInput) },
                    async { resolveIds(current.bansInput) },
                ).awaitAll()

                val req = DraftRequestDto(
                    mapId = mapId,
                    phase = current.phase,
                    allies = allies,
                    enemies = enemies,
                    bans = bans,
                )
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
                    onFailure = { e ->
                        _state.update { it.copy(loading = false, error = e.message) }
                    },
                )
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
            }
        }
    }

    private suspend fun resolveIds(input: String): List<Int> {
        val tokens = input.split(',', ';').map { it.trim() }.filter { it.isNotEmpty() }
        return tokens.mapNotNull { token ->
            token.toIntOrNull()
                ?: repo.searchBrawler(token).getOrNull()?.firstOrNull()?.id
        }
    }
}
