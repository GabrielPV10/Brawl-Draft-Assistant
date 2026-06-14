# Algoritmo de draft

## Fórmula

```
Score(b, mapa, aliados, enemigos, fase, jugador) =
    w1 · winrate_mapa(b)
  + w2 · counter_score(b, enemigos)
  + w3 · sinergia(b, aliados)
  + w4 · pickrate_relativo(b)
  − w5 · ban_risk(b, fase)
  − w6 · counterable_score(b)
  + w7 · personal_proficiency(b, jugador)
```

Los siete pesos viven en `.env` (`W1_WINRATE_MAPA`, …, `W7_PERSONAL_PROFICIENCY`) y se cargan vía `ScoringWeights`. Cambiarlos no requiere redeploy.

## Factores

| Factor                 | Qué mide                                                          | Fuente                         |
|------------------------|--------------------------------------------------------------------|--------------------------------|
| `winrate_mapa`         | Tasa de victorias del brawler en el mapa específico                | Brawlify scrape                |
| `counter_score`        | Qué tan bien le gana a los enemigos ya pickeados                   | Brawlify + matriz derivada     |
| `sinergia`             | Qué tan bien encaja con los aliados ya pickeados                   | Brawlify team comps            |
| `pickrate_relativo`    | Qué tan usado es en ese mapa (señal de meta)                       | Brawlify                       |
| `ban_risk`             | Riesgo de que el enemigo lo banee si es first pick                 | Pickrate + winrate globales    |
| `counterable_score`    | Qué tan fácil es countearlo (penaliza first pick)                  | Matriz de counters             |
| `personal_proficiency` | Qué tan bien lo juega el jugador del slot (0..2)                   | API oficial Supercell + battlelog |

## Ajuste por fase del draft

| Fase         | Prioridad                          | Pesos elevados                       | Pesos reducidos                |
|--------------|-------------------------------------|--------------------------------------|--------------------------------|
| `first_pick` | Flexibilidad, evitar señuelos       | `w1` (winrate mapa), `w6` (counterable) | `w2` (counter directo)        |
| `mid_picks`  | Balance entre meta y respuesta      | Balance estándar                     | Ninguno                        |
| `last_pick`  | Counter directo al enemigo          | `w2` (counter), `w3` (sinergia)      | `w6` (counterable ya no importa) |

El ajuste real vive en `ScoringEngine._adjust_weights(phase)` (stub por ahora).

## Personal proficiency (Fase 2)

Por brawler que tiene el jugador, calculamos un dominio 0-100:

```
personal_proficiency(b, j) =
    0.30 · normalizar(trofeos_brawler[b, j])
  + 0.20 · (nivel_poder[b, j] / 11)
  + 0.15 · gadgets_desbloqueados[b, j]
  + 0.15 · star_powers_desbloqueados[b, j]
  + 0.20 · winrate_reciente[b, j]
```

Implementación: `app/services/supercell.py::proficiency_score`.

## Lógica de equipo (Fase 2)

Cuando el request lleva `profile_id` + `slot`, la recomendación se filtra por:

1. Brawler debe estar desbloqueado por el jugador de ese slot.
2. El factor `personal_proficiency` se multiplica por `w7` (peso fuerte, por defecto 1.2).
3. Si el jugador no tiene un brawler S-tier desbloqueado, automáticamente cae del top.

Ejemplo del plan: si Diego no tiene Bonnie a nivel 11 pero sí Piper, el sistema sugiere Piper para su slot aunque Bonnie sea S-tier global.

## Próximos pasos del algoritmo

1. Implementar `_adjust_weights` con la tabla de fase.
2. Implementar `_enumerate_candidates` (excluir bans/aliados/enemigos).
3. Implementar cada sub-factor con queries reales contra `map_stats` y `synergies`.
4. Tests de regresión con casos del plan (Out in the Open, etc.).
