package com.brawldraft.assistant.ui.draft

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.brawldraft.assistant.data.DraftRepository
import com.brawldraft.assistant.data.api.dto.BrawlerDto
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto
import com.brawldraft.assistant.data.api.dto.DraftRequestDto
import com.brawldraft.assistant.data.api.dto.MapDto
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// Etapas del draft guiado.
enum class DraftStage { BANS, PICKING, DONE }

enum class Team { OURS, ENEMY }

// Un turno de pick: quién elige y con qué fase se le pide al motor de scoring.
data class PickTurn(val team: Team, val phase: DraftPhase)

// Orden real del draft competitivo de Brawl Stars: 1-2-2-1.
// Nosotros (first pick) → rival x2 → nosotros x2 → rival (last pick).
val PICK_ORDER: List<PickTurn> = listOf(
    PickTurn(Team.OURS, DraftPhase.FIRST_PICK),  // 1
    PickTurn(Team.ENEMY, DraftPhase.MID_PICKS),  // 2
    PickTurn(Team.ENEMY, DraftPhase.MID_PICKS),  // 3
    PickTurn(Team.OURS, DraftPhase.MID_PICKS),   // 4
    PickTurn(Team.OURS, DraftPhase.MID_PICKS),   // 5
    PickTurn(Team.ENEMY, DraftPhase.LAST_PICK),  // 6
)

const val MAX_BANS = 6

// Estado del buscador de brawlers compartido por el paso activo (ban o pick).
data class SearchState(
    val query: String = "",
    val suggestions: List<BrawlerDto> = emptyList(),
    val expanded: Boolean = false,
)

data class DraftUiState(
    // Mapa
    val mapQuery: String = "Hard Rock Mine · Gem Grab",
    val mapSuggestions: List<MapDto> = emptyList(),
    val selectedMap: MapDto? = MapDto(id = 15000007, name = "Hard Rock Mine", slug = "hard-rock-mine", game_mode = "Gem Grab"),
    val mapDropdownExpanded: Boolean = false,
    // Máquina de estados del draft
    val stage: DraftStage = DraftStage.BANS,
    val turnIndex: Int = 0,
    val bans: List<BrawlerDto> = emptyList(),
    val allies: List<BrawlerDto> = emptyList(),
    val enemies: List<BrawlerDto> = emptyList(),
    // Buscador activo
    val search: SearchState = SearchState(),
    // Recomendaciones (solo en turnos nuestros)
    val loading: Boolean = false,
    val recommendations: List<DraftRecommendationDto> = emptyList(),
    val computedInMs: Int = 0,
    val error: String? = null,
) {
    val currentTurn: PickTurn? get() = PICK_ORDER.getOrNull(turnIndex)
    val isOurTurn: Boolean get() = currentTurn?.team == Team.OURS
}

class DraftViewModel(
    private val repo: DraftRepository = DraftRepository(),
) : ViewModel() {

    private val _state = MutableStateFlow(DraftUiState())
    val state: StateFlow<DraftUiState> = _state.asStateFlow()

    // --------------------------------------------------------- Mapa

    private var mapSearchJob: Job? = null

    fun setMapQuery(text: String) {
        _state.update { it.copy(mapQuery = text, selectedMap = null, mapDropdownExpanded = true) }
        mapSearchJob?.cancel()
        if (text.length < 2) {
            _state.update { it.copy(mapSuggestions = emptyList()) }
            return
        }
        mapSearchJob = viewModelScope.launch {
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

    // --------------------------------------------------------- Buscador de brawlers

    private var brawlerSearchJob: Job? = null

    fun setSearchQuery(query: String) {
        _state.update { it.copy(search = it.search.copy(query = query, expanded = true)) }
        brawlerSearchJob?.cancel()
        if (query.length < 2) {
            _state.update { it.copy(search = it.search.copy(suggestions = emptyList())) }
            return
        }
        brawlerSearchJob = viewModelScope.launch {
            delay(250)
            repo.searchBrawler(query).onSuccess { results ->
                val taken = takenBrawlerIds()
                val filtered = results.filter { it.id !in taken }
                _state.update { it.copy(search = it.search.copy(suggestions = filtered, expanded = filtered.isNotEmpty())) }
            }
        }
    }

    fun dismissSearchDropdown() = _state.update { it.copy(search = it.search.copy(expanded = false)) }

    /** IDs ya usados en bans/aliados/enemigos: no deben reaparecer en sugerencias. */
    private fun takenBrawlerIds(): Set<Int> {
        val s = _state.value
        return (s.bans + s.allies + s.enemies).map { it.id }.toSet()
    }

    private fun clearSearch() {
        _state.update { it.copy(search = SearchState()) }
    }

    // --------------------------------------------------------- Fase de bans

    fun addBan(brawler: BrawlerDto) {
        val s = _state.value
        if (s.bans.size >= MAX_BANS || brawler.id in takenBrawlerIds()) return
        _state.update { it.copy(bans = it.bans + brawler) }
        clearSearch()
    }

    fun removeBan(brawler: BrawlerDto) {
        _state.update { it.copy(bans = it.bans.filter { b -> b.id != brawler.id }) }
    }

    fun startPicks() {
        if (_state.value.selectedMap == null) {
            _state.update { it.copy(error = "Selecciona un mapa antes de empezar") }
            return
        }
        _state.update { it.copy(stage = DraftStage.PICKING, turnIndex = 0, error = null) }
        clearSearch()
        fetchRecommendationsIfOurTurn()
    }

    // --------------------------------------------------------- Picks por turno

    /** Agrega el brawler al equipo del turno actual y avanza. Usado por buscador y por tap en recomendación. */
    fun pickCurrentTurn(brawler: BrawlerDto) {
        val s = _state.value
        val turn = s.currentTurn ?: return
        if (brawler.id in takenBrawlerIds()) return

        _state.update {
            when (turn.team) {
                Team.OURS  -> it.copy(allies = it.allies + brawler)
                Team.ENEMY -> it.copy(enemies = it.enemies + brawler)
            }
        }
        advanceTurn()
    }

    private fun advanceTurn() {
        val next = _state.value.turnIndex + 1
        clearSearch()
        if (next >= PICK_ORDER.size) {
            _state.update { it.copy(turnIndex = next, stage = DraftStage.DONE, recommendations = emptyList()) }
            return
        }
        _state.update { it.copy(turnIndex = next, recommendations = emptyList()) }
        fetchRecommendationsIfOurTurn()
    }

    private fun fetchRecommendationsIfOurTurn() {
        val s = _state.value
        val turn = s.currentTurn ?: return
        if (turn.team != Team.OURS) return
        val mapId = s.selectedMap?.id ?: return

        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            val req = DraftRequestDto(
                mapId = mapId,
                phase = turn.phase,
                allies = s.allies.map { it.id },
                enemies = s.enemies.map { it.id },
                bans = s.bans.map { it.id },
                topN = 5,
            )
            repo.recommend(req).fold(
                onSuccess = { resp ->
                    _state.update { it.copy(loading = false, recommendations = resp.recommendations, computedInMs = resp.computedInMs) }
                },
                onFailure = { e -> _state.update { it.copy(loading = false, error = e.message) } },
            )
        }
    }

    // --------------------------------------------------------- Control general

    /** Reinicia el draft completo (mantiene el mapa seleccionado). */
    fun resetDraft() {
        _state.update {
            DraftUiState(
                mapQuery = it.mapQuery,
                selectedMap = it.selectedMap,
            )
        }
    }
}
