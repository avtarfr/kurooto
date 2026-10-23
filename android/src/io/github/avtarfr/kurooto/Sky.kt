package io.github.avtarfr.kurooto

import android.graphics.RuntimeShader
import android.os.Build
import androidx.annotation.RequiresApi
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.ImageShader
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.ShaderBrush
import androidx.compose.ui.graphics.TileMode
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.graphics.toArgb
import androidx.compose.material3.MaterialTheme
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import java.util.Calendar
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * The sky behind the main screen (0.7.0), in the language of the dashboard's SYSTEMS view (home.js): living tissue.
 * Back to front: the sky, tinted by the hour (cool at night, warm near dawn and dusk, a little moss by day, as the
 * landing page's day); two deep soft forms for depth; a faint mesh of specks round the core; the core itself, a
 * membrane (a translucent body with a bright rim, two looser rims outside it and a denser nucleus, breathing very
 * slowly) that crosses the top of the screen with the hour as the site's sun does (low at the left at dawn, high at
 * noon, low at the right at dusk; quieter and cooler at night); six tapered nerves leaving it, drifting like threads;
 * and a fine grain so nothing bands. Colours from the theme (Material You's accents, or the palette's). Strongest on
 * Today and the pairing screen (`strength` 1), quieter behind Inbox and Phone.
 *
 * Android 13+: one AGSL shader (RuntimeShader) draws it on the GPU, at half resolution, scaled up. Android 12: the same picture from Canvas paths,
 * moving. Android 6 to 11: the same picture, still (drawn when the screen draws; no animation loop).
 * Motion: drift cycles take minutes and a breath about nine seconds, at small amplitudes; about 14 frames a second
 * while the app is in front, none when it isn't, and none at all with "Remove animations" (a still frame at the
 * hour). `scroll` (Today's scroll, px) moves the layers at different rates, a gentle parallax. Nothing is allocated
 * per frame. `fixedHour`: a set hour instead of the clock (the demo's "hour" extra, to look at any time of day).
 */
@Composable
fun Sky(owner: LifecycleOwner, strength: () -> Float, scroll: () -> Float, modifier: Modifier = Modifier, fixedHour: Float? = null) {
    val scheme = MaterialTheme.colorScheme
    val k = LocalKurooto.current
    val reduced = LocalReducedMotion.current
    fixed = fixedHour
    val animate = !reduced && Build.VERSION.SDK_INT >= 31
    var time by remember { mutableFloatStateOf(seed()) }
    var hour by remember(fixedHour) { mutableFloatStateOf(fixedHour ?: hourNow()) }
    LaunchedEffect(owner, animate) {
        owner.repeatOnLifecycle(Lifecycle.State.STARTED) {
            hour = hourNow()
            var last = 0L
            var checked = 0L
            while (true) {
                if (animate) {
                    withFrameMillis { ms ->
                        if (last != 0L) time += (ms - last).coerceAtMost(100) / 1000f
                        last = ms
                        if (ms - checked > 60_000) { hour = hourNow(); checked = ms } // the cell moves on with the hour
                    }
                    delay(60) // about 14 frames a second: plenty for a drift this slow
                } else {
                    delay(60_000)
                    hour = hourNow()
                }
            }
        }
    }
    val p = remember(scheme, k) { SkyColors(scheme.background, scheme.primary, scheme.secondary, scheme.tertiary, scheme.onBackground, k.light) }
    if (Build.VERSION.SDK_INT >= 33) {
        val sh = remember { SkyShader() }
        // drawn at half the screen's resolution into its own layer, then scaled up: the picture is soft, so this
        // looks the same and costs a quarter of the GPU time
        BoxWithConstraints(modifier) {
            Canvas(
                Modifier.size(maxWidth / 2, maxHeight / 2).graphicsLayer {
                    scaleX = 2f
                    scaleY = 2f
                    transformOrigin = TransformOrigin(0f, 0f)
                    compositingStrategy = CompositingStrategy.Offscreen
                },
            ) { sh.draw(this, p, time, hour, strength(), scroll() / 2f) }
        }
    } else {
        val grain = remember(k.light) { grain(k.light) }
        Canvas(modifier) { drawSkyCanvas(this, p, time, hour, strength(), scroll(), grain) }
    }
}

/** The colours the sky is made of, from the theme. */
private class SkyColors(val base: Color, val a: Color, val b: Color, val c: Color, val ink: Color, val light: Boolean)

/** A start for the drift that differs between launches, so the sky isn't the same picture every time. */
private fun seed(): Float = (System.currentTimeMillis() / 1000 % 3600).toFloat()

private fun hourNow(): Float = fixed ?: realHour()

private var fixed: Float? = null

private fun realHour(): Float {
    val c = Calendar.getInstance()
    return c.get(Calendar.HOUR_OF_DAY) + c.get(Calendar.MINUTE) / 60f
}

// ---------- the hour: the sky's tint and where the core is ----------

/** The tint at the top of the sky for an hour: keyframes through the day, light or dark. */
private fun skyTint(hour: Float, light: Boolean): Color {
    // hour, then colour: night, before dawn, dawn, morning, noon, afternoon, dusk, evening, night
    val hs = floatArrayOf(0f, 4.5f, 6.5f, 9f, 13f, 16.5f, 18.5f, 20.5f, 24f)
    val cs = if (light) longArrayOf(0xFFDDE4E6, 0xFFE4E3EA, 0xFFF8E3CC, 0xFFF2F0DC, 0xFFEAF0D8, 0xFFF3EDD6, 0xFFF6DCCB, 0xFFE2DDE6, 0xFFDDE4E6)
    else longArrayOf(0xFF0A1418, 0xFF13141F, 0xFF2A1D12, 0xFF18200F, 0xFF141F10, 0xFF1C1F10, 0xFF2B1914, 0xFF16131D, 0xFF0A1418)
    var i = 0
    while (i < hs.size - 2 && hour >= hs[i + 1]) i++
    val f = ((hour - hs[i]) / (hs[i + 1] - hs[i])).coerceIn(0f, 1f)
    val s = f * f * (3 - 2 * f)
    return lerp(Color(cs[i]), Color(cs[i + 1]), s)
}

/** Where the core is: x and y as fractions of the width, its radius as a fraction of the width, and whether it's day.
 *  By day (06:00 to 18:30) it rises from the middle, is highest at noon and sets past the right edge, always in the
 *  top right, clear of the title at the left; at night it crosses again, smaller and quieter. */
private class Core(var x: Float = 0f, var y: Float = 0f, var r: Float = 0f, var day: Boolean = true)

private fun coreAt(hour: Float, aspect: Float, out: Core) {
    val day = hour in 6f..18.5f
    val p = if (day) (hour - 6f) / 12.5f else (((hour + 24f - 18.5f) % 24f) / 11.5f)
    val arc = sin(PI.toFloat() * p)
    out.day = day
    out.x = 0.50f + 0.56f * p
    out.r = if (day) 0.27f else 0.22f
    out.y = aspect * (0.26f - 0.17f * arc) - 0.04f
}

/** How much the core's light shows at an hour: full by day, less at night. */
private fun coreLight(day: Boolean, light: Boolean): Float = if (day) 1f else if (light) 0.55f else 0.6f

// ---------- Android 13+: the shader ----------

private const val AGSL = """
uniform float2 size;
uniform float time;
uniform float strength;
uniform float scroll;
uniform float light;
uniform float3 core;     // x, y, r in px
uniform float glow;      // how much the core shows (night: less)
layout(color) uniform half4 base;
layout(color) uniform half4 top;
layout(color) uniform half4 ca;
layout(color) uniform half4 cb;
layout(color) uniform half4 cc;
layout(color) uniform half4 ink;

const float TAU = 6.2831853;

float hash(float2 p) {
    p = fract(p * float2(443.897, 441.423));
    p += dot(p, p.yx + 19.19);
    return fract((p.x + p.y) * p.x);
}

float vnoise(float2 p) {
    float2 i = floor(p);
    float2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + float2(1.0, 0.0));
    float c = hash(i + float2(0.0, 1.0));
    float d = hash(i + float2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float form(float2 uv, float2 c, float r) {
    float2 d = (uv - c) / r;
    return exp(-dot(d, d) * 1.6);
}

// the dashboard's blob: a radius that wobbles round the angle (home.js blob())
float wob(float a, float t, float seed, float w) {
    return 1.0 + w * (0.5 * sin(2.0 * a + t * 0.55 + seed) + 0.38 * sin(3.0 * a - t * 0.9 + seed * 1.7)
        + 0.22 * sin(5.0 * a + t * 1.4 + seed * 2.3));
}

// a soft line at distance d from an edge, w wide (px)
float edge(float d, float w) {
    return 1.0 - smoothstep(w * 0.5, w * 0.5 + 1.4, abs(d));
}

half4 main(float2 fc) {
    float W = size.x;
    float H = size.y / W;
    float2 uv = fc / W;
    float par = scroll / W;
    float t = time;
    float gy = fc.y / size.y;
    float st = strength;

    // the sky: the hour's tint at the top, the ground below
    half3 col = mix(top.rgb, base.rgb, smoothstep(0.0, 0.85, gy));

    // depth: two large soft forms far back, drifting over minutes
    float2 w = uv + 0.08 * float2(vnoise(uv * 1.2 + float2(t * 0.010, 3.1)), vnoise(uv * 1.2 + float2(7.7, -t * 0.008))) - 0.04;
    float f1 = form(w, float2(0.95 + 0.07 * cos(t * 0.019 + 1.3), 0.62 * H - par * 0.20 + 0.06 * sin(t * 0.015)), 0.70);
    float f2 = form(w, float2(0.12 + 0.09 * sin(t * 0.023 + 2.1), 1.02 * H - par * 0.30 + 0.05 * cos(t * 0.021)), 0.62);
    float fa = light > 0.5 ? 0.20 : 0.30;
    col = mix(col, cc.rgb, f1 * fa * st);
    col = mix(col, cb.rgb, f2 * fa * st);

    // the core, in polar terms round its centre
    float2 cxy = core.xy - float2(0.0, scroll * 0.25);
    float R = core.z;
    float2 d = fc - cxy;
    float rho = length(d);
    float ang = atan(d.y, d.x);
    float breath = 0.5 + 0.5 * sin(t * 0.70);   // about nine seconds
    float tt = t * 0.25;
    float g = glow * (0.08 + 0.92 * st * st);
    float A = light > 0.5 ? 0.85 : 1.15;         // a touch more on dark grounds
    half3 fillc = light > 0.5 ? mix(ca.rgb, base.rgb, 0.35) : ca.rgb;   // fills stay airy on light grounds

    // a faint mesh of specks round it (the dashboard's mesh): strongest near the rims, gone far away
    float cell = W / 15.0;
    float2 gi = floor(fc / cell);
    float2 jp = (gi + 0.2 + 0.6 * float2(hash(gi), hash(gi + 17.0))) * cell;
    float speck = 1.0 - smoothstep(0.8, 2.0, length(fc - jp));
    float near = exp(-max(rho - R, 0.0) / (R * 1.4)) * smoothstep(R * 0.9, R * 1.3, rho);
    col = mix(col, ink.rgb, speck * near * 0.10 * g);

    // six nerves leave it, tapered (thick at the core, fine far out), drifting like threads
    float far = max(rho - R * 0.95, 0.0) / W;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float a0 = fi * TAU / 6.0 + 0.4 + 0.18 * sin(t * 0.021 + fi * 2.3);
        float bend = (0.55 + 0.25 * sin(fi * 1.9)) * sin(far * 3.2 + t * 0.045 + fi * 1.7) * far * 1.6;
        float da = ang - (a0 + bend);
        da = da - TAU * floor((da + 3.14159265) / TAU);   // into -pi..pi
        float dist = da * rho;
        float wdt = mix(1.0, R * 0.04, exp(-far * 5.0));
        float fade = exp(-far * 1.6) * smoothstep(R * 0.92, R * 1.05, rho);
        half3 nc = mix(ca.rgb, mod(fi, 2.0) < 0.5 ? cb.rgb : cc.rgb, clamp(far * 1.5, 0.0, 1.0));
        col = mix(col, nc, edge(dist, wdt) * fade * 0.42 * A * g);
        // the thinner second fibre beside it
        float da2 = da - 0.07 * sin(far * 9.0 + t * 0.06 + fi);
        col = mix(col, nc, edge(da2 * rho, 1.0) * fade * 0.22 * A * g);
    }

    // the membrane: two looser outer rims (each a beat later), then the body with its bright rim
    float r2 = R * (1.52 + 0.03 * breath) * wob(ang, tt * 0.6, 4.1, 0.13);
    float r1 = R * (1.24 + 0.025 * breath) * wob(ang, tt * 0.8, 2.9, 0.10);
    float r0 = R * (1.00 + 0.04 * breath) * wob(ang, tt, 1.7, 0.085);
    col = mix(col, ca.rgb, (1.0 - smoothstep(r2 - 1.0, r2 + 1.0, rho)) * 0.05 * A * g);
    col = mix(col, ca.rgb, edge(rho - r2, 1.2) * 0.16 * A * g);
    col = mix(col, ca.rgb, (1.0 - smoothstep(r1 - 1.0, r1 + 1.0, rho)) * 0.07 * A * g);
    col = mix(col, ca.rgb, edge(rho - r1, 1.3) * 0.24 * A * g);
    float inside = 1.0 - smoothstep(r0 - 1.2, r0 + 1.2, rho);
    float body = mix(0.13, 0.07, smoothstep(0.0, r0, rho)) + 0.12 * smoothstep(r0 * 0.7, r0, rho);
    col = mix(col, fillc, inside * body * A * g);
    col = mix(col, mix(ca.rgb, ink.rgb, 0.25), edge(rho - r0, 2.4) * 0.55 * A * g);
    // the nucleus: denser, drifting a little inside
    float2 nxy = cxy + R * float2(0.06 * sin(t * 0.21), 0.05 * cos(t * 0.17));
    float2 nd = fc - nxy;
    float nr = R * (0.58 + 0.03 * breath) * wob(atan(nd.y, nd.x), tt * 1.3, 6.2, 0.07);
    float nl = length(nd);
    float nucleus = 1.0 - smoothstep(nr - 1.2, nr + 1.2, nl);
    // lit from the top left, as the dashboard's nucleus
    float lit = 1.0 - clamp(length(nd + nr * float2(0.25, 0.3)) / (nr * 1.4), 0.0, 1.0);
    col = mix(col, mix(fillc, light > 0.5 ? base.rgb : ink.rgb, 0.22 * lit), nucleus * (0.12 + 0.14 * lit) * A * g);
    col = mix(col, ca.rgb, edge(nl - nr, 1.2) * 0.35 * A * g);

    // grain, fixed to the pixel: breaks up banding, never shimmers
    col += half3((hash(fc) - 0.5) * (light > 0.5 ? 0.024 : 0.030));
    return half4(col, 1.0);
}
"""

@RequiresApi(33)
private class SkyShader {
    private val shader = RuntimeShader(AGSL)
    private val brush = ShaderBrush(shader)
    private val core = Core()

    fun draw(s: DrawScope, p: SkyColors, time: Float, hour: Float, strength: Float, scroll: Float) {
        val w = s.size.width
        val h = s.size.height
        if (w <= 0f || h <= 0f) return
        coreAt(hour, h / w, core)
        val top = lerp(p.base, skyTint(hour, p.light), 0.75f * (0.4f + 0.6f * strength))
        shader.setFloatUniform("size", w, h)
        shader.setFloatUniform("time", time)
        shader.setFloatUniform("strength", strength)
        shader.setFloatUniform("scroll", scroll)
        shader.setFloatUniform("light", if (p.light) 1f else 0f)
        shader.setFloatUniform("core", core.x * w, core.y * w, core.r * w)
        shader.setFloatUniform("glow", coreLight(core.day, p.light))
        shader.setColorUniform("base", p.base.toArgb())
        shader.setColorUniform("top", top.toArgb())
        shader.setColorUniform("ca", p.a.toArgb())
        shader.setColorUniform("cb", p.b.toArgb())
        shader.setColorUniform("cc", p.c.toArgb())
        shader.setColorUniform("ink", p.ink.toArgb())
        s.drawRect(brush)
    }
}

// ---------- Android 6 to 12: the same picture from Canvas paths ----------

private val canvasCore = Core()
private val rim = Path()

/** The dashboard's blob outline into [rim]: 48 points, joined by curves through their midpoints. */
private fun blob(cx: Float, cy: Float, r: Float, t: Float, seed: Float, wob: Float) {
    val n = 48
    rim.reset()
    var px0 = 0f
    var py0 = 0f
    var lx = 0f
    var ly = 0f
    for (i in 0..n) {
        val a = (i % n) * 2f * PI.toFloat() / n
        val k = 1 + wob * (0.5f * sin(2 * a + t * 0.55f + seed) + 0.38f * sin(3 * a - t * 0.9f + seed * 1.7f) + 0.22f * sin(5 * a + t * 1.4f + seed * 2.3f))
        val x = cx + cos(a) * r * k
        val y = cy + sin(a) * r * k
        if (i == 0) { px0 = x; py0 = y; rim.moveTo(x, y) } else rim.quadraticTo(lx, ly, (lx + x) / 2, (ly + y) / 2)
        lx = x
        ly = y
    }
    rim.quadraticTo(lx, ly, px0, py0)
    rim.close()
}

private fun drawSkyCanvas(s: DrawScope, p: SkyColors, time: Float, hour: Float, strength: Float, scroll: Float, grain: ImageBitmap) {
    val w = s.size.width
    val h = s.size.height
    if (w <= 0f || h <= 0f) return
    val top = lerp(p.base, skyTint(hour, p.light), 0.75f * (0.4f + 0.6f * strength))
    s.drawRect(Brush.verticalGradient(0f to top, 0.85f to p.base, startY = 0f, endY = h))
    val t = time
    val par = scroll / w
    val aspect = h / w
    val fa = (if (p.light) 0.20f else 0.30f) * strength
    fun form(c: Color, cx: Float, cy: Float, r: Float) {
        val center = Offset(cx * w, cy * w)
        s.drawCircle(Brush.radialGradient(0f to c.copy(alpha = fa), 0.55f to c.copy(alpha = fa * 0.45f), 1f to c.copy(alpha = 0f), center = center, radius = r * w * 1.25f), r * w * 1.25f, center)
    }
    form(p.c, 0.95f + 0.07f * cos(t * 0.019f + 1.3f), 0.62f * aspect - par * 0.20f + 0.06f * sin(t * 0.015f), 0.70f)
    form(p.b, 0.12f + 0.09f * sin(t * 0.023f + 2.1f), 1.02f * aspect - par * 0.30f + 0.05f * cos(t * 0.021f), 0.62f)
    coreAt(hour, aspect, canvasCore)
    val g = coreLight(canvasCore.day, p.light) * (0.08f + 0.92f * strength * strength) * (if (p.light) 1f else 1.15f)
    val cx = canvasCore.x * w
    val cy = canvasCore.y * w - scroll * 0.25f
    val r = canvasCore.r * w
    val breath = 0.5f + 0.5f * sin(t * 0.7f)
    val tt = t * 0.25f
    // nerves: six tapered curves outwards, in three widths
    for (i in 0 until 6) {
        val a0 = i * 2f * PI.toFloat() / 6f + 0.4f + 0.18f * sin(t * 0.021f + i * 2.3f)
        val bend = (0.55f + 0.25f * sin(i * 1.9f)) * 0.35f * sin(t * 0.045f + i * 1.7f)
        var x0 = cx + cos(a0) * r
        var y0 = cy + sin(a0) * r
        for (seg in 0 until 3) {
            val d1 = r + w * 0.22f * (seg + 1)
            val a1 = a0 + bend * (seg + 1) / 3f
            val x1 = cx + cos(a1) * d1
            val y1 = cy + sin(a1) * d1
            val alpha = 0.42f * g * (1f - seg / 3.2f)
            s.drawLine(p.a.copy(alpha = alpha), Offset(x0, y0), Offset(x1, y1), strokeWidth = r * 0.04f / (seg + 1) + 1f)
            x0 = x1
            y0 = y1
        }
    }
    // the membrane: outer rims, body, rim, nucleus
    blob(cx, cy, r * (1.52f + 0.03f * breath), tt * 0.6f, 4.1f, 0.13f)
    s.drawPath(rim, p.a.copy(alpha = 0.05f * g))
    s.drawPath(rim, p.a.copy(alpha = 0.16f * g), style = Stroke(1.2f))
    blob(cx, cy, r * (1.24f + 0.025f * breath), tt * 0.8f, 2.9f, 0.10f)
    s.drawPath(rim, p.a.copy(alpha = 0.07f * g))
    s.drawPath(rim, p.a.copy(alpha = 0.24f * g), style = Stroke(1.3f))
    blob(cx, cy, r * (1f + 0.04f * breath), tt, 1.7f, 0.085f)
    s.drawPath(rim, p.a.copy(alpha = 0.12f * g))
    s.drawPath(rim, lerp(p.a, p.ink, 0.25f).copy(alpha = 0.55f * g), style = Stroke(2.4f))
    blob(cx + r * 0.06f * sin(t * 0.21f), cy + r * 0.05f * cos(t * 0.17f), r * (0.58f + 0.03f * breath), tt * 1.3f, 6.2f, 0.07f)
    s.drawPath(rim, p.a.copy(alpha = 0.18f * g))
    s.drawPath(rim, p.a.copy(alpha = 0.35f * g), style = Stroke(1.2f))
    s.drawRect(ShaderBrush(ImageShader(grain, TileMode.Repeated, TileMode.Repeated)), size = Size(w, h))
}

/** A small tile of fixed grain (made once): breaks up the gradients' banding. */
private fun grain(light: Boolean): ImageBitmap {
    val n = 96
    val px = IntArray(n * n)
    val rnd = java.util.Random(7)
    for (i in px.indices) {
        val g = rnd.nextInt(256)
        px[i] = ((if (light) 7 else 9) shl 24) or (g shl 16) or (g shl 8) or g
    }
    return android.graphics.Bitmap.createBitmap(px, n, n, android.graphics.Bitmap.Config.ARGB_8888).asImageBitmap()
}
