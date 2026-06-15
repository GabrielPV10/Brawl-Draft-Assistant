package com.brawldraft.assistant.ui.draft

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto
import com.brawldraft.assistant.data.api.dto.MapDto

// Colores de score: verde ≥0.6, amarillo ≥0.3, rojo <0.3
private fun scoreColor(score: Float): Color = when {
    score >= 0.6f -> Color(0xFF4CAF50)
    score >= 0.3f -> Color(0xFFFFC107)
    else          -> Color(0xFFF44336)
}

// Etiquetas legibles para cada factor del breakdown
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
            "Brawl Draft Assistant",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            "Escribe el nombre del mapa y selecciónalo del listado.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        // Campo de búsqueda de mapa con dropdown
        MapSearchField(
            query = state.mapQuery,
            suggestions = state.mapSuggestions,
            expanded = state.mapDropdownExpanded,
            selectedMap = state.selectedMap,
            onQueryChange = vm::setMapQuery,
            onSelect = vm::selectMap,
            onDismiss = vm::dismissMapDropdown,
        )

        Text("Fase del draft", style = MaterialTheme.typography.labelLarge)
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            DraftPhase.entries.forEach { phase ->
                FilterChip(
                    selected = state.phase == phase,
                    onClick = { vm.setPhase(phase) },
                    label = { Text(phase.name.replace('_', ' ').lowercase()) },
                )
            }
        }

        OutlinedTextField(
            value = state.alliesInput,
            onValueChange = vm::setAllies,
            label = { Text("Aliados pickeados") },
            placeholder = { Text("shelly, colt o 16000000") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.enemiesInput,
            onValueChange = vm::setEnemies,
            label = { Text("Enemigos pickeados") },
            placeholder = { Text("bull, brock o 16000003") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.bansInput,
            onValueChange = vm::setBans,
            label = { Text("Baneados") },
            placeholder = { Text("piper, nita") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Button(
                onClick = vm::recommend,
                enabled = !state.loading,
                modifier = Modifier.weight(1f),
            ) { Text("Recomendar") }
            OutlinedButton(
                onClick = vm::fetchDummy,
                enabled = !state.loading,
                modifier = Modifier.weight(1f),
            ) { Text("Probar (dummy)") }
        }

        if (state.loading) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
                CircularProgressIndicator()
            }
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

        if (state.recommendations.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            Text(
                "Top ${state.recommendations.size} · ${state.computedInMs} ms",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.height((state.recommendations.size * 200).dp),
            ) {
                itemsIndexed(state.recommendations) { index, rec ->
                    RecommendationCard(rec, rank = index + 1)
                }
            }
        }
    }
}

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
            placeholder = { Text("Ej: Hard Rock Mine, Har…") },
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
                if (index < suggestions.lastIndex) {
                    HorizontalDivider()
                }
            }
        }
    }
}

@Composable
private fun RecommendationCard(rec: DraftRecommendationDto, rank: Int) {
    val maxScore = 1.5f
    val normalizedScore = (rec.score.toFloat() / maxScore).coerceIn(0f, 1f)
    val color = scoreColor(normalizedScore)

    Card(
        modifier = Modifier.fillMaxWidth(),
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
                    Text(
                        rec.brawlerName,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
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
                Text(it, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }

            if (rec.breakdown.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                rec.breakdown.entries
                    .filter { (_, v) -> v != 0.0 }
                    .sortedByDescending { (_, v) -> kotlin.math.abs(v) }
                    .take(4)
                    .forEach { (key, value) ->
                        FactorRow(
                            label = FACTOR_LABELS[key] ?: key,
                            value = value.toFloat(),
                        )
                    }
            }
        }
    }
}

@Composable
private fun AnimatedBar(progress: Float, color: Color) {
    var target by remember { mutableFloatStateOf(0f) }
    val animated by animateFloatAsState(
        targetValue = target,
        animationSpec = tween(600),
        label = "score_bar",
    )
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
