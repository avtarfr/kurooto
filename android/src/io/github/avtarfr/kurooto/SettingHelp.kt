package io.github.avtarfr.kurooto

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExperimentalMaterial3ExpressiveApi
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * The settings guide on the phone (0.8.10): every setting's entry (what it does, its values and default, when you'd change
 * it, what it costs or sends, what it depends on), from assets/settings-help.json. tools/gen_settings_guide.py writes that
 * file with the user wiki's Settings guide, from the same source, so the two never differ.
 *
 * For the Settings pane's long-press: `val help = rememberSettingHelp()`, then `help?.helpFor(key)` and, for the entry it
 * gives, [SettingHelpSheet]. A key is a computer setting ("brain.main", "calls.views") or the app's own, as Prefs keeps it
 * ("vivid", "bedsideAuto", "senses.steps", "places.on"; "app.vivid" works too). A setting with no entry gives null: show
 * nothing rather than a guess. The file is read once, off the main thread ([load]).
 */
object SettingHelp {
    const val ASSET = "settings-help.json"

    /** One setting's entry. [children]: for a box of several settings (availability.night), the settings in it. */
    data class Entry(
        val key: String,
        val tip: String,
        val what: String,
        val values: String,
        val default: String,
        val whenToChange: String,
        val cost: String,
        val needs: String,
        val group: String,
        val url: String,
        val children: List<Entry> = emptyList(),
    )

    /** The parsed guide: entries by key, and each feature group's title. */
    class Guide(val entries: Map<String, Entry>, val groups: Map<String, String>) {
        /** The entry for a setting, or null. The app's own keys are found with or without "app.". */
        fun helpFor(key: String): Entry? = entries[key] ?: entries["app.$key"]

        /** The title of an entry's feature group ("Phone calls and the call line"). */
        fun groupTitle(e: Entry): String = groups[e.group] ?: ""

        /** Every entry whose words contain all of [words] (lowercase), for a search over settings. */
        fun search(words: List<String>): List<Entry> = entries.values.filter { e ->
            val hay = listOf(e.key, e.tip, e.what, e.values, e.whenToChange, e.cost, e.needs).joinToString("\n").lowercase()
            words.all { hay.contains(it) }
        }
    }

    @Volatile private var guide: Guide? = null

    /** The guide if it's been loaded, else null (call [load] first, or use [rememberSettingHelp]). */
    fun loaded(): Guide? = guide

    /** Read and parse the asset once, on an IO thread; later calls return the same guide. Null if it can't be read. */
    suspend fun load(c: Context): Guide? = guide ?: withContext(Dispatchers.IO) {
        guide ?: try {
            parse(c.applicationContext.assets.open(ASSET).use { it.readBytes().toString(Charsets.UTF_8) }).also { guide = it }
        } catch (_: Exception) {
            null
        }
    }

    /** The asset's JSON as a [Guide]: {page, groups: [{id, title}], settings: {key: {...}}, parents: {key: {...}}}. */
    fun parse(json: String): Guide {
        val o = JSONObject(json)
        val page = o.optString("page")
        val groups = mutableMapOf<String, String>()
        o.optJSONArray("groups")?.let { a -> for (i in 0 until a.length()) a.optJSONObject(i)?.let { groups[it.optString("id")] = it.optString("title") } }
        val out = HashMap<String, Entry>()
        val s = o.optJSONObject("settings") ?: JSONObject()
        for (key in s.keys()) {
            val e = s.getJSONObject(key)
            out[key] = Entry(
                key = key,
                tip = e.optString("tip"),
                what = e.optString("what"),
                values = e.optString("values"),
                default = e.optString("default"),
                whenToChange = e.optString("when"),
                cost = e.optString("cost"),
                needs = e.optString("needs"),
                group = e.optString("g"),
                url = if (page.isEmpty()) "" else page + "#" + e.optString("anchor"),
            )
        }
        val p = o.optJSONObject("parents") ?: JSONObject()
        for (key in p.keys()) {
            if (out.containsKey(key)) continue
            val e = p.getJSONObject(key)
            val kids = e.optJSONArray("children")?.let { a -> (0 until a.length()).mapNotNull { out[a.optString(it)] } } ?: emptyList()
            out[key] = Entry(
                key = key, tip = e.optString("tip"), what = "", values = "", default = "", whenToChange = "", cost = "", needs = "",
                group = e.optString("g"), url = if (page.isEmpty()) "" else page + "#" + e.optString("anchor"), children = kids,
            )
        }
        return Guide(out, groups)
    }
}

/** The guide, once it's loaded off the main thread (null until then, or if the asset is missing). */
@Composable
fun rememberSettingHelp(): SettingHelp.Guide? {
    val c = LocalContext.current
    var g by remember { mutableStateOf(SettingHelp.loaded()) }
    LaunchedEffect(Unit) { if (g == null) g = SettingHelp.load(c) }
    return g
}

/**
 * A setting's whole entry in a bottom sheet (drag it up for the rest, down or back to close): its group, the setting's name,
 * the tip as the headline, then what it does, its values and default, when to change it, what it costs or sends and what it
 * depends on, and a button to its entry in the user wiki.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterial3ExpressiveApi::class)
@Composable
fun SettingHelpSheet(guide: SettingHelp.Guide, entry: SettingHelp.Entry, onClose: () -> Unit) {
    val c = LocalContext.current
    val k = MaterialTheme.colorScheme
    ModalBottomSheet(onDismissRequest = onClose, sheetState = rememberModalBottomSheetState(), containerColor = k.surfaceContainerLow) {
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp).padding(bottom = 24.dp).navigationBarsPadding(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val group = guide.groupTitle(entry)
            if (group.isNotEmpty()) Text(group, style = MaterialTheme.typography.labelLarge, color = k.primary)
            Text(entry.key.removePrefix("app."), style = MaterialTheme.typography.labelMedium.copy(fontFamily = FontFamily.Monospace), color = k.onSurfaceVariant)
            Text(guideText(entry.tip, k.surfaceContainerHighest), style = MaterialTheme.typography.titleLargeEmphasized, color = k.onSurface)
            if (entry.what.isNotEmpty()) Text(guideText(entry.what, k.surfaceContainerHighest), style = MaterialTheme.typography.bodyLarge, color = k.onSurface)
            if (entry.children.isEmpty()) {
                Surface(shape = MaterialTheme.shapes.large, color = k.surfaceContainerHigh, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        HelpRow("Values", entry.values)
                        HelpRow("Default", entry.default)
                        HelpRow("When to change it", entry.whenToChange)
                        HelpRow("What it costs or sends", entry.cost)
                        HelpRow("Depends on", entry.needs)
                    }
                }
            } else {
                for (kid in entry.children) {
                    Surface(shape = MaterialTheme.shapes.large, color = k.surfaceContainerHigh, modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(kid.key.removePrefix(entry.key + "."), style = MaterialTheme.typography.labelLarge.copy(fontFamily = FontFamily.Monospace), color = k.primary)
                            Text(guideText(kid.tip, k.surfaceContainerHighest), style = MaterialTheme.typography.bodyLarge, color = k.onSurface)
                            HelpRow("Default", kid.default)
                        }
                    }
                }
            }
            if (entry.url.isNotEmpty()) {
                FilledTonalButton(
                    onClick = { try { c.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(entry.url))) } catch (_: Exception) {} },
                    shapes = ButtonDefaults.shapes(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("In the settings guide") }
            }
        }
    }
}

@Composable
private fun HelpRow(label: String, text: String) {
    if (text.isEmpty()) return
    val k = MaterialTheme.colorScheme
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = k.onSurfaceVariant)
        Text(guideText(text, k.surfaceContainerHighest), style = MaterialTheme.typography.bodyMedium, color = k.onSurface)
    }
}

/** The entry's text with its `code` in a monospace face on a faint chip. */
private fun guideText(text: String, chip: Color): AnnotatedString = buildAnnotatedString {
    val parts = text.split('`')
    parts.forEachIndexed { i, part ->
        if (i % 2 == 1 && i < parts.size - 1) withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = chip)) { append(part) } else append(part)
    }
}
