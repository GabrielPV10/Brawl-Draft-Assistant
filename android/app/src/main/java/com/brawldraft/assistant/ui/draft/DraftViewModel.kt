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

/**
 * Construye el orden 1-2-2-1 del draft según quién tiene el primer pick.
 *
 * El draft SIEMPRE es: equipoA(1) → equipoB(2) → equipoA(2) → equipoB(1), donde
 * A es el de primer pick. Lo único que cambia es si "nosotros" somos A o B.
 *
 * - weAreFirst=true  (moneda AZUL): nuestros picks en posiciones 1, 4, 5.
 * - weAreFirst=false (moneda ROJA): somos el equipo de último pick → 2, 3, 6.
 *
 * La fase para el motor: posición 0 = FIRST_PICK, posición 5 = LAST_PICK, resto MID.
 */
fun buildPickOrder(weAreFirst: Boolean): List<PickTurn> {
    val teams = if (weAreFirst) {
        listOf(Team.OURS, Team.ENEMY, Team.ENEMY, Team.OURS, Team.OURS, Team.ENEMY)
    } else {
        listOf(Team.ENEMY, Team.OURS, Team.OURS, Team.ENEMY, Team.ENEMY, Team.OURS)
    }
    return teams.mapIndexed { i, team ->
        val phase = when (i) {
            0    -> DraftPhase.FIRST_PICK
            5    -> DraftPhase.LAST_PICK
            else -> DraftPhase.MID_PICKS
        }
        PickTurn(team, phase)
    }
}

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
    val weAreFirstPick: Boolean = true,   // moneda azul = true, roja = false
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
    val pickOrder: List<PickTurn> get() = buildPickOrder(weAreFirstPick)
    val currentTurn: PickTurn? get() = pickOrder.getOrNull(turnIndex)
    val isOurTurn: Boolean get() = currentTurn?.team == Team.OURS

    /** ¿Hay algo que deshacer? (un ban, un pick, o salir de la fase de picks). */
    val canUndo: Boolean get() = when (stage) {
        DraftStage.BANS    -> bans.isNotEmpty()
        DraftStage.PICKING -> turnIndex > 0 || bans.isNotEmpty()
        DraftStage.DONE    -> true
    }
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
            delay(120)
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

    /** Elige el lado: true = moneda azul (primer pick), false = moneda roja (último pick). */
    fun setSide(firstPick: Boolean) {
        _state.update { it.copy(weAreFirstPick = firstPick) }
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
        if (next >= _state.value.pickOrder.size) {
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

    /**
     * Deshace el último paso del draft. Si te equivocaste en un pick, retrocede un
     * turno y borra ese brawler (sin reiniciar todo). Funciona en cadena.
     *
     * - En PICKING turno >0: quita el pick del turno anterior y vuelve a ese turno.
     * - En PICKING turno 0: regresa a la fase de bans.
     * - En DONE: vuelve al último turno y deshace el último pick.
     */
    fun undoLastStep() {
        val s = _state.value
        when (s.stage) {
            DraftStage.BANS -> {
                // En bans, deshacer = quitar el último baneado agregado.
                if (s.bans.isNotEmpty()) {
                    _state.update { it.copy(bans = it.bans.dropLast(1)) }
                    clearSearch()
                }
            }
            DraftStage.PICKING -> {
                if (s.turnIndex == 0) {
                    _state.update { it.copy(stage = DraftStage.BANS, recommendations = emptyList(), loading = false) }
                    clearSearch()
                } else {
                    undoTurn(s.turnIndex - 1)
                }
            }
            DraftStage.DONE -> {
                // turnIndex == pickOrder.size; el último turno completado es el último de la lista.
                _state.update { it.copy(stage = DraftStage.PICKING) }
                undoTurn(s.pickOrder.size - 1)
            }
        }
    }

    /** Quita el pick hecho en `targetTurn` (su equipo) y deja ese turno como el activo. */
    private fun undoTurn(targetTurn: Int) {
        val team = _state.value.pickOrder[targetTurn].team
        _state.update {
            val base = when (team) {
                Team.OURS  -> it.copy(allies = it.allies.dropLast(1))
                Team.ENEMY -> it.copy(enemies = it.enemies.dropLast(1))
            }
            base.copy(turnIndex = targetTurn, recommendations = emptyList(), loading = false, error = null)
        }
        clearSearch()
        fetchRecommendationsIfOurTurn()
    }

    // --------------------------------------------------------- Control general

    /** Reinicia el draft completo (mantiene el mapa y el lado elegido). */
    fun resetDraft() {
        _state.update {
            DraftUiState(
                mapQuery = it.mapQuery,
                selectedMap = it.selectedMap,
                weAreFirstPick = it.weAreFirstPick,
            )
        }
    }
}
