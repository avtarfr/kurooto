package io.github.avtarfr.kurooto

import androidx.compose.material3.ColorScheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import com.materialkolor.dynamiccolor.DynamicColor
import com.materialkolor.dynamiccolor.MaterialDynamicColors
import com.materialkolor.hct.Hct
import com.materialkolor.scheme.SchemeExpressive

/**
 * The vivid look (0.7.5): a Material 3 Expressive colour scheme made from one seed colour, so the containers, the bar and
 * the cards are really coloured instead of a pale tint of the wallpaper. Android's own Material You scheme ("tonal spot") is
 * the quietest of Material's styles; this uses the Expressive one, which keeps the hue and lifts the chroma.
 *
 * Used when Look's palette is Material You (0.8.10; the named palettes, Apricot and Kuro, have their own fixed schemes).
 * The seed is the wallpaper's colour (the system's own scheme's primary, Android 12+). A wallpaper with almost no colour (a
 * grey or snowy one) would give a grey scheme, so below [MIN_CHROMA] Kurooto's own olive is the seed (kept in 0.8.10 so
 * Material You looks as it did; Apricot is a palette of its own). "Calm" turns all of this off and brings back the
 * wallpaper's quiet scheme.
 */
object Vivid {
    const val MIN_CHROMA = 16.0
    val BRAND = Color(0xFF3F5626) // kuro's olive: Palettes.kuro's primary

    /** The seed: `wallpaper` (a colour of the system's scheme) if it has colour, else Kurooto's olive. */
    fun seed(wallpaper: Color?): Color {
        if (wallpaper == null) return BRAND
        val hct = Hct.fromInt(wallpaper.toArgb())
        return if (hct.chroma >= MIN_CHROMA) wallpaper else BRAND
    }

    /** A full Compose colour scheme, light or dark, from the seed's Expressive scheme. */
    fun scheme(seed: Color, dark: Boolean): ColorScheme {
        val s = SchemeExpressive(Hct.fromInt(seed.toArgb()), dark, 0.0)
        val m = MaterialDynamicColors()

        fun c(d: DynamicColor) = Color(d.getArgb(s))
        val primary = c(m.primary())
        return if (dark) {
            darkColorScheme(
                primary = primary, onPrimary = c(m.onPrimary()), primaryContainer = c(m.primaryContainer()),
                onPrimaryContainer = c(m.onPrimaryContainer()), inversePrimary = c(m.inversePrimary()),
                secondary = c(m.secondary()), onSecondary = c(m.onSecondary()), secondaryContainer = c(m.secondaryContainer()),
                onSecondaryContainer = c(m.onSecondaryContainer()),
                tertiary = c(m.tertiary()), onTertiary = c(m.onTertiary()), tertiaryContainer = c(m.tertiaryContainer()),
                onTertiaryContainer = c(m.onTertiaryContainer()),
                background = c(m.background()), onBackground = c(m.onBackground()),
                surface = c(m.surface()), onSurface = c(m.onSurface()), surfaceVariant = c(m.surfaceVariant()),
                onSurfaceVariant = c(m.onSurfaceVariant()), surfaceTint = primary,
                inverseSurface = c(m.inverseSurface()), inverseOnSurface = c(m.inverseOnSurface()),
                error = c(m.error()), onError = c(m.onError()), errorContainer = c(m.errorContainer()),
                onErrorContainer = c(m.onErrorContainer()), outline = c(m.outline()), outlineVariant = c(m.outlineVariant()),
                scrim = c(m.scrim()),
                surfaceBright = c(m.surfaceBright()), surfaceDim = c(m.surfaceDim()),
                surfaceContainerLowest = c(m.surfaceContainerLowest()), surfaceContainerLow = c(m.surfaceContainerLow()),
                surfaceContainer = c(m.surfaceContainer()), surfaceContainerHigh = c(m.surfaceContainerHigh()),
                surfaceContainerHighest = c(m.surfaceContainerHighest()),
            )
        } else {
            lightColorScheme(
                primary = primary, onPrimary = c(m.onPrimary()), primaryContainer = c(m.primaryContainer()),
                onPrimaryContainer = c(m.onPrimaryContainer()), inversePrimary = c(m.inversePrimary()),
                secondary = c(m.secondary()), onSecondary = c(m.onSecondary()), secondaryContainer = c(m.secondaryContainer()),
                onSecondaryContainer = c(m.onSecondaryContainer()),
                tertiary = c(m.tertiary()), onTertiary = c(m.onTertiary()), tertiaryContainer = c(m.tertiaryContainer()),
                onTertiaryContainer = c(m.onTertiaryContainer()),
                background = c(m.background()), onBackground = c(m.onBackground()),
                surface = c(m.surface()), onSurface = c(m.onSurface()), surfaceVariant = c(m.surfaceVariant()),
                onSurfaceVariant = c(m.onSurfaceVariant()), surfaceTint = primary,
                inverseSurface = c(m.inverseSurface()), inverseOnSurface = c(m.inverseOnSurface()),
                error = c(m.error()), onError = c(m.onError()), errorContainer = c(m.errorContainer()),
                onErrorContainer = c(m.onErrorContainer()), outline = c(m.outline()), outlineVariant = c(m.outlineVariant()),
                scrim = c(m.scrim()),
                surfaceBright = c(m.surfaceBright()), surfaceDim = c(m.surfaceDim()),
                surfaceContainerLowest = c(m.surfaceContainerLowest()), surfaceContainerLow = c(m.surfaceContainerLow()),
                surfaceContainer = c(m.surfaceContainer()), surfaceContainerHigh = c(m.surfaceContainerHigh()),
                surfaceContainerHighest = c(m.surfaceContainerHighest()),
            )
        }
    }
}
