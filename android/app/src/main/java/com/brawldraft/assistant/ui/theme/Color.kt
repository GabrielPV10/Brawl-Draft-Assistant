package com.brawldraft.assistant.ui.theme

import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color

// ──────────────────────────────────────────────────────────────────
// Paleta "Amber" de Brawl Stars: fuego (rojo→naranja→oro), morado y verde,
// sobre un fondo oscuro cálido. Estética gamer.
// ──────────────────────────────────────────────────────────────────

// Fuego
val Ember        = Color(0xFFFF3D00)  // rojo-naranja intenso
val FireOrange   = Color(0xFFFF6F00)  // naranja principal
val FireBright   = Color(0xFFFF9100)  // naranja brillante
val Gold         = Color(0xFFFFC400)  // oro / amarillo
val GoldLight    = Color(0xFFFFD740)

// Morado (botas/top de Amber)
val Purple       = Color(0xFF9C27B0)
val PurpleDeep   = Color(0xFF6A1B9A)
val PurpleLight  = Color(0xFFCE93D8)

// Verde (trenza)
val BraidGreen   = Color(0xFF43A047)
val BraidGreenLt = Color(0xFF81C784)

// Rojo (acento)
val AmberRed     = Color(0xFFE53935)

// Fondo oscuro cálido
val BgDeep       = Color(0xFF160C09)  // casi negro con tinte cálido
val BgRaised     = Color(0xFF1F1310)
val SurfaceWarm  = Color(0xFF2A1A14)
val SurfaceWarm2 = Color(0xFF3A241C)
val OutlineWarm  = Color(0xFF5A3A2C)

// Texto
val WarmWhite    = Color(0xFFFFF3E6)
val WarmMuted    = Color(0xFFD7B5A0)

// ──────────────────────────────────────────────────────────────────
// Degradados (Brush) reutilizables
// ──────────────────────────────────────────────────────────────────

/** Degradado de fuego horizontal: rojo → naranja → oro. Para botones y acentos. */
val FireGradient = Brush.linearGradient(
    colors = listOf(Ember, FireOrange, Gold),
)

/** Degradado fuego → morado, para detalles "épicos". */
val FirePurpleGradient = Brush.linearGradient(
    colors = listOf(FireOrange, Ember, Purple),
)

/** Fondo general de la app: oscuro con leve calidez hacia abajo. */
val AppBackgroundGradient = Brush.verticalGradient(
    colors = listOf(BgDeep, BgRaised, BgDeep),
)

/** Degradado tenue para tarjetas (sutil, no satura). */
val CardGradient = Brush.verticalGradient(
    colors = listOf(SurfaceWarm2, SurfaceWarm),
)

/** Botón deshabilitado: grises cálidos apagados. */
val DisabledGradient = Brush.linearGradient(
    colors = listOf(SurfaceWarm2, SurfaceWarm),
)
