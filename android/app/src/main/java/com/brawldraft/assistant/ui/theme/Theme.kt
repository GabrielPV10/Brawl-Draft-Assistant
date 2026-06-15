package com.brawldraft.assistant.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Esquema de color fijo (sin dynamicColor): siempre el tema fuego de Amber,
// en modo oscuro, independiente del fondo de pantalla del usuario.
private val AmberFireColorScheme = darkColorScheme(
    primary = FireOrange,
    onPrimary = WarmWhite,
    primaryContainer = PurpleDeep,
    onPrimaryContainer = WarmWhite,

    secondary = Purple,
    onSecondary = WarmWhite,
    secondaryContainer = PurpleDeep,
    onSecondaryContainer = PurpleLight,

    tertiary = Gold,
    onTertiary = BgDeep,

    background = BgDeep,
    onBackground = WarmWhite,

    surface = SurfaceWarm,
    onSurface = WarmWhite,
    surfaceVariant = SurfaceWarm2,
    onSurfaceVariant = WarmMuted,

    outline = OutlineWarm,
    outlineVariant = OutlineWarm,

    error = AmberRed,
    onError = WarmWhite,
    errorContainer = Color(0xFF3D1212),
    onErrorContainer = Color(0xFFFFB4AB),
)

@Composable
fun BrawlDraftAssistantTheme(
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = AmberFireColorScheme,
        typography = Typography,
        content = content,
    )
}
