package cloud.shawnstronger.orbit

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val LightColors = lightColorScheme(
    primary = Color(0xFF4355A5),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE1E5FF),
    onPrimaryContainer = Color(0xFF121D55),
    secondary = Color(0xFF5E6650),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFE3E9D5),
    onSecondaryContainer = Color(0xFF1B2413),
    tertiary = Color(0xFF855D16),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFFFDEA4),
    onTertiaryContainer = Color(0xFF2A1A00),
    background = Color(0xFFFAF8F3),
    onBackground = Color(0xFF1C1C1A),
    surface = Color(0xFFFFFCF7),
    onSurface = Color(0xFF1C1C1A),
    surfaceVariant = Color(0xFFECEAE4),
    onSurfaceVariant = Color(0xFF484743),
    outline = Color(0xFF797873),
    outlineVariant = Color(0xFFCAC8C2),
    error = Color(0xFFBA1A1A),
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    scrim = Color(0xFF000000),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFBBC3FF),
    onPrimary = Color(0xFF10205E),
    primaryContainer = Color(0xFF293B89),
    onPrimaryContainer = Color(0xFFE1E5FF),
    secondary = Color(0xFFC7CFB7),
    onSecondary = Color(0xFF303728),
    secondaryContainer = Color(0xFF464E3D),
    onSecondaryContainer = Color(0xFFE3E9D5),
    tertiary = Color(0xFFF5BF67),
    onTertiary = Color(0xFF472A00),
    tertiaryContainer = Color(0xFF654200),
    onTertiaryContainer = Color(0xFFFFDEA4),
    background = Color(0xFF131311),
    onBackground = Color(0xFFE5E2DD),
    surface = Color(0xFF1B1B18),
    onSurface = Color(0xFFE5E2DD),
    surfaceVariant = Color(0xFF484743),
    onSurfaceVariant = Color(0xFFCAC8C2),
    outline = Color(0xFF93918C),
    outlineVariant = Color(0xFF484743),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    scrim = Color(0xFF000000),
)

private val OrbitTypography = Typography().run {
    copy(
        displaySmall = displaySmall.copy(fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp),
        headlineLarge = headlineLarge.copy(fontWeight = FontWeight.Bold, letterSpacing = (-0.3).sp),
        headlineMedium = headlineMedium.copy(fontWeight = FontWeight.Bold),
        headlineSmall = headlineSmall.copy(fontWeight = FontWeight.SemiBold),
        titleLarge = titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelLarge = labelLarge.copy(fontWeight = FontWeight.SemiBold),
    )
}

private val OrbitShapes = Shapes(
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
)

@Composable
fun OrbitTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        typography = OrbitTypography,
        shapes = OrbitShapes,
        content = content,
    )
}
