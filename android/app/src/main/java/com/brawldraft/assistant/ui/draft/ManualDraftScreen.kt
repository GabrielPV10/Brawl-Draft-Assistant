package com.brawldraft.assistant.ui.draft

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.brawldraft.assistant.data.api.dto.DraftPhase
import com.brawldraft.assistant.data.api.dto.DraftRecommendationDto

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
            "Selección manual del draft. Ingresa IDs Supercell separados por coma.",
            style = MaterialTheme.typography.bodySmall,
        )

        OutlinedTextField(
            value = state.mapIdInput,
            onValueChange = vm::setMapId,
            label = { Text("Map ID") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
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
            label = { Text("Aliados pickeados (IDs)") },
            placeholder = { Text("16000000, 16000054") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.enemiesInput,
            onValueChange = vm::setEnemies,
            label = { Text("Enemigos pickeados (IDs)") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.bansInput,
            onValueChange = vm::setBans,
            label = { Text("Baneados (IDs)") },
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
            ) {
                Text("Recomendar")
            }
            OutlinedButton(
                onClick = vm::fetchDummy,
                enabled = !state.loading,
                modifier = Modifier.weight(1f),
            ) {
                Text("Probar (dummy)")
            }
        }

        if (state.loading) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
            ) {
                CircularProgressIndicator()
            }
        }
        state.error?.let { err ->
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                ),
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
            Spacer(Modifier.height(8.dp))
            Text(
                "Top ${state.recommendations.size} · ${state.computedInMs} ms",
                style = MaterialTheme.typography.labelLarge,
            )
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.height((state.recommendations.size * 130).dp),
            ) {
                items(state.recommendations) { rec ->
                    RecommendationCard(rec, rank = state.recommendations.indexOf(rec) + 1)
                }
            }
        }
    }
}

@Composable
private fun RecommendationCard(rec: DraftRecommendationDto, rank: Int) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "#$rank · ${rec.brawlerName}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "%.2f".format(rec.score),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            rec.explanation?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            if (rec.breakdown.isNotEmpty()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    rec.breakdown.entries.joinToString(" · ") { (k, v) -> "$k=%.2f".format(v) },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}
