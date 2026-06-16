package com.brawldraft.assistant.ui.draft

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.InputChip
import androidx.compose.material3.InputChipDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.brawldraft.assistant.data.api.dto.BrawlerDto
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto
import com.brawldraft.assistant.data.api.dto.MapDto
import com.brawldraft.assistant.ui.theme.FireGradient
import com.brawldraft.assistant.ui.theme.GamerButton

private val ALLY_COLOR = Color(0xFF4CAF50)
private val ENEMY_COLOR = Color(0xFFF44336)
private val BAN_COLOR = Color(0xFF9E9E9E)

private fun scoreColor(score: Float): Color = when {
    score >= 0.6f -> Color(0xFF4CAF50)
    score >= 0.3f -> Color(0xFFFFC107)
    else          -> Color(0xFFF44336)
}

private val FACTOR_LABELS = mapOf(
    "winrate_mapa"         to "Winrate mapa",
    "counter_score"        to "Counter",
    "sinergia"             to "Sinergia",
    "pickrate_relativo"    to "Pickrate",
    "ban_risk"             to "Ban risk",
    "counterable"          to "Counterable",
    "personal_proficiency" to "Proficiencia",
)

@Composable
fun ManualDraftScreen(
    vm: DraftViewModel = viewModel(),
    modifier: Modifier = Modifier,
) {
    val state by vm.state.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            "BRAWL DRAFT",
            style = MaterialTheme.typography.headlineMedium.copy(brush = FireGradient),
            fontWeight = FontWeight.Black,
        )

        // Selección de mapa: por modo (cascada) o por buscador.
        ModeMapSelector(state = state, vm = vm)
        if (state.catalogLoading && state.catalog.isEmpty()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                Text(
                    "Cargando modos… (primer uso puede tardar ~30s)",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        MapSearchField(
            query = state.mapQuery,
            suggestions = state.mapSuggestions,
            expanded = state.mapDropdownExpanded,
            selectedMap = state.selectedMap,
            onQueryChange = vm::setMapQuery,
            onSelect = vm::selectMap,
            onDismiss = vm::dismissMapDropdown,
        )

        DraftProgressBar(stage = state.stage, turnIndex = state.turnIndex, pickOrder = state.pickOrder)

        // Estado actual de los tres equipos (siempre visible una vez hay picks/bans).
        TeamsSummary(
            allies = state.allies,
            enemies = state.enemies,
            bans = state.bans,
            onRemoveBan = if (state.stage == DraftStage.BANS) vm::removeBan else null,
        )

        when (state.stage) {
            DraftStage.BANS    -> BansPhase(state, vm)
            DraftStage.PICKING -> PickingPhase(state, vm)
            DraftStage.DONE    -> DonePhase(state, vm)
        }

        state.error?.let { err ->
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    "Error: $err",
                    modifier = Modifier.padding(12.dp),
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
            }
        }
    }
}

// ──────────────────────────────────────────────── Barra de progreso del draft

@Composable
private fun DraftProgressBar(stage: DraftStage, turnIndex: Int, pickOrder: List<PickTurn>) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Punto de bans
            StepDot(
                label = "B",
                color = BAN_COLOR,
                active = stage == DraftStage.BANS,
                done = stage != DraftStage.BANS,
            )
            Text("›", color = MaterialTheme.colorScheme.onSurfaceVariant)
            // Puntos de cada pick (el color refleja quién elige en cada turno)
            pickOrder.forEachIndexed { index, turn ->
                val color = if (turn.team == Team.OURS) ALLY_COLOR else ENEMY_COLOR
                StepDot(
                    label = "${index + 1}",
                    color = color,
                    active = stage == DraftStage.PICKING && turnIndex == index,
                    done = stage == DraftStage.DONE || (stage == DraftStage.PICKING && turnIndex > index),
                )
            }
        }
        Text(
            "🟢 tú · 🔴 rival · orden 1-2-2-1",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun StepDot(label: String, color: Color, active: Boolean, done: Boolean) {
    val bg = when {
        active -> color
        done   -> color.copy(alpha = 0.30f)
        else   -> MaterialTheme.colorScheme.surfaceVariant
    }
    val fg = if (active) Color.White else color
    Box(
        modifier = Modifier.size(26.dp).background(bg, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold, color = fg)
    }
}

// ──────────────────────────────────────────────── Resumen de equipos

@Composable
private fun TeamsSummary(
    allies: List<BrawlerDto>,
    enemies: List<BrawlerDto>,
    bans: List<BrawlerDto>,
    onRemoveBan: ((BrawlerDto) -> Unit)?,
) {
    if (allies.isEmpty() && enemies.isEmpty() && bans.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (allies.isNotEmpty()) ChipLine("Tu equipo", allies, ALLY_COLOR, null)
        if (enemies.isNotEmpty()) ChipLine("Rival", enemies, ENEMY_COLOR, null)
        if (bans.isNotEmpty()) ChipLine("Baneados (${bans.size}/$MAX_BANS)", bans, BAN_COLOR, onRemoveBan)
    }
}

@Composable
private fun ChipLine(
    label: String,
    brawlers: List<BrawlerDto>,
    color: Color,
    onRemove: ((BrawlerDto) -> Unit)?,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = color, fontWeight = FontWeight.Bold)
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            brawlers.chunked(3).forEach { rowChips ->
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    rowChips.forEach { brawler ->
                        BrawlerChip(brawler, color, onRemove)
                    }
                }
            }
        }
    }
}

@Composable
private fun BrawlerChip(brawler: BrawlerDto, color: Color, onRemove: ((BrawlerDto) -> Unit)?) {
    InputChip(
        selected = true,
        onClick = { onRemove?.invoke(brawler) },
        enabled = onRemove != null,
        label = { Text(brawler.name, style = MaterialTheme.typography.labelMedium) },
        trailingIcon = onRemove?.let {
            { Icon(Icons.Default.Close, contentDescription = "Quitar", modifier = Modifier.size(14.dp)) }
        },
        colors = InputChipDefaults.inputChipColors(
            selectedContainerColor = color.copy(alpha = 0.18f),
            selectedLabelColor = color,
            selectedTrailingIconColor = color,
            disabledSelectedContainerColor = color.copy(alpha = 0.18f),
        ),
    )
}

// ──────────────────────────────────────────────── Fase de bans

@Composable
private fun BansPhase(state: DraftUiState, vm: DraftViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            "Fase de bans · ${state.bans.size}/$MAX_BANS",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "Agrega los 6 brawlers baneados (3 tuyos + 3 del rival). Puedes empezar con menos.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (state.bans.size < MAX_BANS) {
            BrawlerSearchBox(
                search = state.search,
                hint = "Busca un brawler para banear…",
                onQueryChange = vm::setSearchQuery,
                onSelect = vm::addBan,
                onDismiss = vm::dismissSearchDropdown,
            )
        }

        // Selector de moneda: ¿somos primer pick (azul) o último pick (roja)?
        Spacer(Modifier.height(2.dp))
        Text("¿Qué moneda te tocó?", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
            CoinOption(
                emoji = "🔵",
                title = "Azul",
                subtitle = "Primer pick",
                color = Color(0xFF2196F3),
                selected = state.weAreFirstPick,
                onClick = { vm.setSide(true) },
                modifier = Modifier.weight(1f),
            )
            CoinOption(
                emoji = "🔴",
                title = "Roja",
                subtitle = "Último pick",
                color = ENEMY_COLOR,
                selected = !state.weAreFirstPick,
                onClick = { vm.setSide(false) },
                modifier = Modifier.weight(1f),
            )
        }

        GamerButton(
            text = "EMPEZAR PICKS →",
            onClick = vm::startPicks,
            enabled = state.selectedMap != null,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
private fun CoinOption(
    emoji: String,
    title: String,
    subtitle: String,
    color: Color,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val border = if (selected) color else MaterialTheme.colorScheme.outline
    Surface(
        onClick = onClick,
        shape = MaterialTheme.shapes.medium,
        color = if (selected) color.copy(alpha = 0.16f) else MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(if (selected) 2.dp else 1.dp, border),
        modifier = modifier,
    ) {
        Column(
            modifier = Modifier.padding(12.dp).fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(emoji, style = MaterialTheme.typography.headlineSmall)
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold,
                color = if (selected) color else MaterialTheme.colorScheme.onSurface)
            Text(subtitle, style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

// ──────────────────────────────────────────────── Fase de picks

@Composable
private fun PickingPhase(state: DraftUiState, vm: DraftViewModel) {
    val turn = state.currentTurn ?: return
    val turnNum = state.turnIndex + 1

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        // Cabecera del turno
        val (titulo, color) = if (turn.team == Team.OURS) {
            "Turno $turnNum/6 · Tu pick" to ALLY_COLOR
        } else {
            "Turno $turnNum/6 · Pick del rival" to ENEMY_COLOR
        }
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = color.copy(alpha = 0.12f),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                titulo,
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = color,
            )
        }

        if (turn.team == Team.ENEMY) {
            Text(
                "¿Qué brawler eligió el rival?",
                style = MaterialTheme.typography.bodyMedium,
            )
            BrawlerSearchBox(
                search = state.search,
                hint = "Busca el pick del rival…",
                onQueryChange = vm::setSearchQuery,
                onSelect = vm::pickCurrentTurn,
                onDismiss = vm::dismissSearchDropdown,
            )
        } else {
            // Turno nuestro: selector de estrategia + recomendaciones + búsqueda manual
            StrategySelector(selected = state.strategy, onSelect = vm::setStrategy)

            if (state.loading) {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                    CircularProgressIndicator()
                }
            }
            if (state.recommendations.isNotEmpty()) {
                Text(
                    "Recomendados · ${state.computedInMs} ms · toca para elegir",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                state.recommendations.forEachIndexed { index, rec ->
                    RecommendationCard(
                        rec = rec,
                        rank = index + 1,
                        onClick = {
                            vm.pickCurrentTurn(BrawlerDto(id = rec.brawlerId, name = rec.brawlerName, slug = ""))
                        },
                    )
                }
            }
            Text(
                "¿Prefieres otro? Búscalo:",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            BrawlerSearchBox(
                search = state.search,
                hint = "Elegir otro brawler…",
                onQueryChange = vm::setSearchQuery,
                onSelect = vm::pickCurrentTurn,
                onDismiss = vm::dismissSearchDropdown,
            )
        }

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedButton(
                onClick = vm::undoLastStep,
                enabled = state.canUndo,
                modifier = Modifier.weight(1f),
            ) { Text("← Atrás") }
            OutlinedButton(onClick = vm::resetDraft, modifier = Modifier.weight(1f)) {
                Text("Reiniciar")
            }
        }
    }
}

@Composable
private fun StrategySelector(selected: Strategy, onSelect: (Strategy) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            "¿Qué priorizar?",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        ) {
            Strategy.entries.forEach { strat ->
                FilterChip(
                    selected = selected == strat,
                    onClick = { onSelect(strat) },
                    label = { Text(strat.label, style = MaterialTheme.typography.labelMedium) },
                )
            }
        }
    }
}

// ──────────────────────────────────────────────── Fase final

@Composable
private fun DonePhase(state: DraftUiState, vm: DraftViewModel) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            color = ALLY_COLOR.copy(alpha = 0.12f),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                "✓ Draft completo",
                modifier = Modifier.padding(12.dp),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = ALLY_COLOR,
            )
        }
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            OutlinedButton(onClick = vm::undoLastStep, modifier = Modifier.weight(1f)) {
                Text("← Corregir último")
            }
            GamerButton(
                text = "NUEVO DRAFT",
                onClick = vm::resetDraft,
                modifier = Modifier.weight(1f),
            )
        }
    }
}

// ──────────────────────────────────────────────── Buscador de brawlers reutilizable

@Composable
private fun BrawlerSearchBox(
    search: SearchState,
    hint: String,
    onQueryChange: (String) -> Unit,
    onSelect: (BrawlerDto) -> Unit,
    onDismiss: () -> Unit,
) {
    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = search.query,
            onValueChange = onQueryChange,
            placeholder = { Text(hint, style = MaterialTheme.typography.bodySmall) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            textStyle = MaterialTheme.typography.bodyMedium,
        )
        DropdownMenu(
            expanded = search.expanded && search.suggestions.isNotEmpty(),
            onDismissRequest = onDismiss,
            modifier = Modifier.fillMaxWidth(),
        ) {
            search.suggestions.forEachIndexed { index, brawler ->
                DropdownMenuItem(
                    text = { Text(brawler.name, style = MaterialTheme.typography.bodyMedium) },
                    onClick = { onSelect(brawler) },
                )
                if (index < search.suggestions.lastIndex) HorizontalDivider()
            }
        }
    }
}

// ──────────────────────────────────────────────── Selector mapa por modo (cascada)

@Composable
private fun ModeMapSelector(state: DraftUiState, vm: DraftViewModel) {
    var modeExpanded by remember { mutableStateOf(false) }

    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            "Elige por modo de juego",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            // Dropdown de MODO
            Box(modifier = Modifier.weight(1f)) {
                DropdownAnchor(
                    label = "Modo",
                    value = state.selectedMode,
                    placeholder = "Elegir…",
                    enabled = state.catalog.isNotEmpty(),
                    onClick = { modeExpanded = true },
                )
                DropdownMenu(
                    expanded = modeExpanded,
                    onDismissRequest = { modeExpanded = false },
                    modifier = Modifier.heightIn(max = 360.dp),
                ) {
                    state.catalog.forEach { mm ->
                        DropdownMenuItem(
                            text = { Text("${mm.mode}  ·  ${mm.maps.size}", style = MaterialTheme.typography.bodyMedium) },
                            onClick = {
                                modeExpanded = false
                                vm.setMode(mm.mode)
                            },
                        )
                    }
                }
            }

            // Dropdown de MAPA (depende del modo elegido)
            Box(modifier = Modifier.weight(1f)) {
                DropdownAnchor(
                    label = "Mapa",
                    value = state.selectedMap?.name,
                    placeholder = "Elegir…",
                    enabled = state.mapsForSelectedMode.isNotEmpty(),
                    onClick = { vm.toggleModeMapDropdown(true) },
                )
                DropdownMenu(
                    expanded = state.modeMapDropdownExpanded && state.mapsForSelectedMode.isNotEmpty(),
                    onDismissRequest = { vm.toggleModeMapDropdown(false) },
                    modifier = Modifier.heightIn(max = 360.dp),
                ) {
                    state.mapsForSelectedMode.forEach { map ->
                        DropdownMenuItem(
                            text = { Text(map.name, style = MaterialTheme.typography.bodyMedium) },
                            onClick = { vm.selectMapFromCatalog(map) },
                        )
                    }
                }
            }
        }
    }
}

/** Campo con apariencia de input que abre un menú al tocarlo (etiqueta + valor + chevron). */
@Composable
private fun DropdownAnchor(
    label: String,
    value: String?,
    placeholder: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        enabled = enabled,
        shape = MaterialTheme.shapes.small,
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    value ?: placeholder,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    color = if (value != null) MaterialTheme.colorScheme.onSurface
                            else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Icon(
                Icons.Default.KeyboardArrowDown,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// ──────────────────────────────────────────────── Buscador de mapa

@Composable
private fun MapSearchField(
    query: String,
    suggestions: List<MapDto>,
    expanded: Boolean,
    selectedMap: MapDto?,
    onQueryChange: (String) -> Unit,
    onSelect: (MapDto) -> Unit,
    onDismiss: () -> Unit,
) {
    Box(modifier = Modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = query,
            onValueChange = onQueryChange,
            label = { Text("Mapa") },
            placeholder = { Text("Ej: Hard Rock Mine…") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
            supportingText = selectedMap?.let {
                { Text("ID ${it.id} · ${it.game_mode}", style = MaterialTheme.typography.labelSmall) }
            },
            isError = selectedMap == null && query.isNotEmpty(),
        )
        DropdownMenu(
            expanded = expanded && suggestions.isNotEmpty(),
            onDismissRequest = onDismiss,
            modifier = Modifier.fillMaxWidth(),
        ) {
            suggestions.forEachIndexed { index, map ->
                DropdownMenuItem(
                    text = {
                        Column {
                            Text(map.name, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                            Text(
                                "${map.game_mode} · ID ${map.id}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    },
                    onClick = { onSelect(map) },
                )
                if (index < suggestions.lastIndex) HorizontalDivider()
            }
        }
    }
}

// ──────────────────────────────────────────────── Tarjeta de recomendación

@Composable
private fun RecommendationCard(rec: DraftRecommendationDto, rank: Int, onClick: () -> Unit) {
    val maxScore = 1.5f
    val normalizedScore = (rec.score.toFloat() / maxScore).coerceIn(0f, 1f)
    val color = scoreColor(normalizedScore)

    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = MaterialTheme.shapes.small,
                        color = color.copy(alpha = 0.15f),
                        modifier = Modifier.size(28.dp),
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Text(
                                "#$rank",
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = color,
                            )
                        }
                    }
                    Spacer(Modifier.width(10.dp))
                    Text(rec.brawlerName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                }
                Text(
                    "%.2f".format(rec.score),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = color,
                )
            }

            Spacer(Modifier.height(8.dp))
            AnimatedBar(progress = normalizedScore, color = color)

            rec.explanation?.let {
                Spacer(Modifier.height(6.dp))
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            if (rec.breakdown.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                rec.breakdown.entries
                    .filter { (_, v) -> v != 0.0 }
                    .sortedByDescending { (_, v) -> kotlin.math.abs(v) }
                    .take(4)
                    .forEach { (key, value) ->
                        FactorRow(label = FACTOR_LABELS[key] ?: key, value = value.toFloat())
                    }
            }
        }
    }
}

@Composable
private fun AnimatedBar(progress: Float, color: Color) {
    var target by remember { mutableFloatStateOf(0f) }
    val animated by animateFloatAsState(targetValue = target, animationSpec = tween(600), label = "score_bar")
    LaunchedEffect(progress) { target = progress }
    LinearProgressIndicator(
        progress = { animated },
        modifier = Modifier.fillMaxWidth().height(6.dp),
        color = color,
        trackColor = color.copy(alpha = 0.15f),
        strokeCap = StrokeCap.Round,
    )
}

@Composable
private fun FactorRow(label: String, value: Float) {
    val barColor = when {
        value > 0.01f  -> Color(0xFF4CAF50)
        value < -0.01f -> Color(0xFFF44336)
        else           -> MaterialTheme.colorScheme.outlineVariant
    }
    val absNorm = (kotlin.math.abs(value) / 0.6f).coerceIn(0f, 1f)
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.width(100.dp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(8.dp))
        LinearProgressIndicator(
            progress = { absNorm },
            modifier = Modifier.weight(1f).height(4.dp),
            color = barColor,
            trackColor = barColor.copy(alpha = 0.12f),
            strokeCap = StrokeCap.Round,
        )
        Spacer(Modifier.width(8.dp))
        Text(
            "%+.2f".format(value),
            style = MaterialTheme.typography.labelSmall,
            color = barColor,
            modifier = Modifier.width(40.dp),
        )
    }
}
