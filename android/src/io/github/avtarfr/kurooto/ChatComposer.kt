package io.github.avtarfr.kurooto

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.union
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialShapes
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.material3.toShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChange
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import java.io.File

/**
 * The composer (0.8.10): the message box in a pill with the attach button and the camera, and beside it the mic (hold
 * to record a voice note, slide left to cancel) that turns into Send once there's something to send. Above it, while
 * they apply: the slash commands as you type "/", the message you're replying to or editing, the file you're about to
 * send. Files over 10 MB say so before anything goes.
 */
@Composable
fun ChatComposer(cu: ChatUi) {
    val cs = MaterialTheme.colorScheme
    val c = cu.a
    var sheet by remember { mutableStateOf(false) }
    var camUri by remember { mutableStateOf<Uri?>(null) }
    fun picked(u: Uri?) {
        if (u == null) return
        val p = ChatFiles.describe(c, u)
        if (ChatRules.tooBig(p.size)) { cu.say("${p.name} is ${ChatRules.size(p.size)}; the chat carries files up to 10 MB."); return }
        cu.pending = p
        cu.editing = null
        cu.wantFocus = true
    }
    val media = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { picked(it) }
    val doc = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { picked(it) }
    val camera = rememberLauncherForActivityResult(ActivityResultContracts.TakePicture()) { ok -> if (ok) picked(camUri) }
    val mic = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) cu.say("Hold the mic to record a voice note.") else cu.say("The microphone isn't allowed: Settings → Apps → Kurooto → Permissions.")
    }
    val takePhoto = {
        try { camUri = ChatFiles.cameraTarget(c); camera.launch(camUri!!) } catch (_: Exception) { cu.say("There's no camera app to take a photo with.") }
    }
    LaunchedEffect(cu.wantFocus) {
        if (cu.wantFocus) {
            cu.wantFocus = false
            try { cu.focus.requestFocus() } catch (_: Exception) { }
        }
    }
    val enterSends = remember(ChatPrefs.rev) { ChatPrefs.on(c, ChatPrefs.ENTER_SENDS) }
    val commandsOn = remember(ChatPrefs.rev) { ChatPrefs.on(c, ChatPrefs.COMMANDS) }
    val fade = MaterialTheme.motionScheme.fastEffectsSpec<Float>()
    val grow = MaterialTheme.motionScheme.fastSpatialSpec<androidx.compose.ui.unit.IntSize>()
    Column(Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.navigationBars.union(WindowInsets.ime)).padding(start = 8.dp, end = 8.dp, bottom = 8.dp)) {
        // the commands while you type "/…"
        val cmds = if (commandsOn) ChatRules.commands(ChatStore.snap.commands, cu.typed.text, 6) else emptyList()
        AnimatedVisibility(cmds.isNotEmpty(), enter = fadeIn(fade) + expandVertically(grow), exit = fadeOut(fade) + shrinkVertically(grow)) {
            Surface(shape = RoundedCornerShape(24.dp), color = cs.surfaceContainerHigh, modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp)) {
                LazyColumn(Modifier.heightIn(max = 260.dp)) {
                    items(cmds, key = { it[0] }) { x ->
                        Row(
                            Modifier.fillMaxWidth().clickable {
                                val t = "/" + x[0] + " "
                                cu.typed = TextFieldValue(t, TextRange(t.length))
                            }.padding(horizontal = 18.dp, vertical = 12.dp),
                        ) {
                            Text("/" + x[0], style = MaterialTheme.typography.titleSmall, color = cs.primary, modifier = Modifier.width(96.dp))
                            Text(x[1], style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                    }
                }
            }
        }
        // what you're replying to, editing, or sending
        val banner = cu.replyTo != null || cu.editing != null || cu.pending != null
        AnimatedVisibility(banner, enter = fadeIn(fade) + expandVertically(grow), exit = fadeOut(fade) + shrinkVertically(grow)) {
            Banner(cu)
        }
        Row(verticalAlignment = Alignment.Bottom) {
            val rec = cu.recording
            Surface(shape = RoundedCornerShape(28.dp), color = cs.surfaceContainerHigh, modifier = Modifier.weight(1f).heightIn(min = 56.dp)) {
                if (rec != null) Recording(cu, rec)
                else Row(verticalAlignment = Alignment.CenterVertically) {
                    // files only while your computer takes them in the chat (calls.chat_files_inline)
                    val files = ChatStore.snap.on("chat_files_inline")
                    if (files) IconButton({ sheet = true }) { Icon(painterResource(R.drawable.ic_chat_add), contentDescription = "Attach", tint = cs.onSurfaceVariant) }
                    else Spacer(Modifier.width(18.dp))
                    Box(Modifier.weight(1f).padding(vertical = 16.dp)) {
                        if (cu.typed.text.isEmpty()) {
                            Text(
                                if (cu.pending != null) "Add a caption" else "Message", style = MaterialTheme.typography.bodyLarge, color = cs.onSurfaceVariant,
                            )
                        }
                        BasicTextField(
                            value = cu.typed,
                            onValueChange = { cu.typed = it },
                            textStyle = MaterialTheme.typography.bodyLarge.copy(color = cs.onSurface),
                            cursorBrush = SolidColor(cs.primary),
                            maxLines = 6,
                            keyboardOptions = KeyboardOptions(
                                capitalization = KeyboardCapitalization.Sentences,
                                imeAction = if (enterSends) ImeAction.Send else ImeAction.Default,
                            ),
                            keyboardActions = KeyboardActions(onSend = { cu.send() }),
                            modifier = Modifier.fillMaxWidth().focusRequester(cu.focus),
                        )
                    }
                    if (files && cu.typed.text.isEmpty() && cu.pending == null) {
                        IconButton({ takePhoto() }) { Icon(painterResource(R.drawable.ic_chat_camera), contentDescription = "Take a photo", tint = cs.onSurfaceVariant) }
                    } else Spacer(Modifier.width(12.dp))
                }
            }
            Spacer(Modifier.width(8.dp))
            val canSend = cu.typed.text.isNotBlank() || cu.pending != null || cu.editing != null || !ChatStore.snap.on("chat_files_inline")
            SendOrMic(cu, canSend) { mic.launch(Manifest.permission.RECORD_AUDIO) }
        }
    }
    if (sheet) AttachSheet(
        close = { sheet = false },
        photo = { media.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageAndVideo)) },
        camera = { takePhoto() },
        file = { doc.launch(arrayOf("*/*")) },
        voice = { cu.say("Hold the mic button to record; slide left to cancel.") },
    )
}

/** Over the composer: the message you reply to, the one you edit, or the file about to go; × takes it away. */
@Composable
private fun Banner(cu: ChatUi) {
    val cs = MaterialTheme.colorScheme
    val (title, line, icon) = when {
        cu.editing != null -> Triple("Editing", ChatRules.plain(cu.editing!!.text), R.drawable.ic_chat_edit)
        cu.pending != null -> cu.pending!!.let { Triple(it.name, ChatRules.size(it.size), if (it.mime.startsWith("image/")) R.drawable.ic_chat_image else R.drawable.ic_chat_file) }
        else -> cu.replyTo!!.let { m ->
            Triple(
                "Reply to " + if (m.mine) "yourself" else Prefs.assistant(cu.a),
                ChatRules.plain(m.text).replace('\n', ' ').ifEmpty { m.file?.name.orEmpty() },
                R.drawable.ic_chat_reply,
            )
        }
    }
    Surface(shape = RoundedCornerShape(22.dp), color = cs.surfaceContainer, modifier = Modifier.fillMaxWidth().padding(bottom = 6.dp)) {
        Row(Modifier.padding(start = 14.dp, end = 2.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(painterResource(icon), null, Modifier.size(20.dp), tint = cs.tertiary)
            Spacer(Modifier.width(10.dp))
            Box(Modifier.width(3.dp).heightIn(min = 34.dp).background(cs.tertiary, CircleShape))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f).padding(vertical = 8.dp)) {
                Text(title, style = MaterialTheme.typography.labelLarge, color = cs.tertiary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(line, style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            IconButton({
                if (cu.editing != null) { cu.editing = null; cu.typed = TextFieldValue("") }
                else if (cu.pending != null) cu.pending = null
                else cu.replyTo = null
            }) { Icon(painterResource(R.drawable.ic_chat_close), contentDescription = "Cancel") }
        }
    }
}

/** A voice note being recorded: since when, and how far the finger has slid toward cancelling. */
class Rec(val r: ChatFiles.Recorder) {
    var dx by mutableFloatStateOf(0f)
    var started by mutableLongStateOf(System.currentTimeMillis())
}

@Composable
private fun Recording(cu: ChatUi, rec: Rec) {
    val cs = MaterialTheme.colorScheme
    val k = LocalKurooto.current
    val secs by produceState(0L, rec) { while (true) { value = (System.currentTimeMillis() - rec.started) / 1000; delay(250) } }
    Row(Modifier.heightIn(min = 56.dp).padding(horizontal = 18.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(k.bad, CircleShape))
        Spacer(Modifier.width(10.dp))
        Text("%d:%02d".format(secs / 60, secs % 60), style = MaterialTheme.typography.titleMedium, color = cs.onSurface)
        Spacer(Modifier.weight(1f))
        Text(
            "‹ Slide to cancel", style = MaterialTheme.typography.bodyMedium, color = cs.onSurfaceVariant,
            modifier = Modifier.graphicsLayer { translationX = rec.dx * 0.5f; alpha = (1f + rec.dx / 400f).coerceIn(0.2f, 1f) },
        )
    }
}

/** The round button at the composer's end: Send when there's something to send; else the mic, held to record. */
@Composable
private fun SendOrMic(cu: ChatUi, canSend: Boolean, askMic: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    val c = cu.a
    val haptic = LocalHapticFeedback.current
    val haptics = remember(ChatPrefs.rev) { ChatPrefs.on(c, ChatPrefs.HAPTICS) }
    val cancelPx = with(LocalDensity.current) { 120.dp.toPx() }
    val spatial = MaterialTheme.motionScheme.fastSpatialSpec<Float>()
    val big by animateFloatAsState(if (cu.recording != null) 1.25f else 1f, spatial, label = "mic")
    val recShape = MaterialShapes.Cookie9Sided.toShape()
    Box(
        Modifier.size(56.dp)
            .graphicsLayer {
                scaleX = big
                scaleY = big
                translationX = cu.recording?.dx ?: 0f
            }
            .background(cs.primary, if (cu.recording != null) recShape else CircleShape)
            .then(
                if (canSend) Modifier.clickable { cu.send() }
                else Modifier.pointerInput(Unit) {
                    awaitEachGesture {
                        awaitFirstDown(requireUnconsumed = false)
                        if (c.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                            askMic()
                            return@awaitEachGesture
                        }
                        if (cu.demo) { cu.say("Demo: voice notes need a paired phone."); return@awaitEachGesture }
                        val r = ChatFiles.Recorder(c)
                        if (!r.start()) { cu.say("Couldn't start recording."); return@awaitEachGesture }
                        if (haptics) haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                        val rec = Rec(r)
                        cu.recording = rec
                        var cancelled = false
                        while (true) {
                            val ev = awaitPointerEvent()
                            val ch = ev.changes.firstOrNull() ?: break
                            if (!ch.pressed) break
                            rec.dx = (rec.dx + ch.positionChange().x).coerceAtMost(0f)
                            ch.consume()
                            if (!cancelled && rec.dx < -cancelPx) {
                                cancelled = true
                                if (haptics) haptic.performHapticFeedback(HapticFeedbackType.Reject)
                            }
                        }
                        cu.recording = null
                        if (cancelled) { r.cancel(); return@awaitEachGesture }
                        val f: File? = r.stop()
                        if (f == null) { cu.say("Hold the mic to record a voice note."); return@awaitEachGesture }
                        val p = ChatFiles.Picked(Uri.fromFile(f), f.name, f.length(), "audio/mp4")
                        cu.pending = null
                        val re = cu.replyTo?.id.orEmpty()
                        cu.replyTo = null
                        ChatFiles.send(c, ChatStore.current, p, "", re)
                    }
                },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            painterResource(if (canSend) R.drawable.ic_chat_send else R.drawable.ic_chat_mic),
            contentDescription = if (canSend) "Send" else "Hold to record a voice note",
            tint = cs.onPrimary,
        )
    }
}

/** The attach sheet: a photo or video (the photo picker), the camera, any file, a voice note. */
@Composable
private fun AttachSheet(close: () -> Unit, photo: () -> Unit, camera: () -> Unit, file: () -> Unit, voice: () -> Unit) {
    val cs = MaterialTheme.colorScheme
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(onDismissRequest = close, sheetState = state, containerColor = cs.surfaceContainerLow) {
        Text("Send", style = MaterialTheme.typography.titleLargeEmphasized, modifier = Modifier.padding(start = 24.dp, bottom = 8.dp))
        Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 12.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
            Tile("Photo or video", R.drawable.ic_chat_image, MaterialShapes.Cookie9Sided, cs.primaryContainer, cs.onPrimaryContainer) { close(); photo() }
            Tile("Camera", R.drawable.ic_chat_camera, MaterialShapes.Clover4Leaf, cs.secondaryContainer, cs.onSecondaryContainer) { close(); camera() }
            Tile("File", R.drawable.ic_chat_file, MaterialShapes.Pentagon, cs.tertiaryContainer, cs.onTertiaryContainer) { close(); file() }
            Tile("Voice note", R.drawable.ic_chat_mic, MaterialShapes.Sunny, cs.surfaceContainerHighest, cs.onSurface) { close(); voice() }
        }
        Text(
            "Up to 10 MB each. With your computer off, what you send waits on your call line.",
            style = MaterialTheme.typography.bodySmall, color = cs.onSurfaceVariant,
            modifier = Modifier.padding(start = 24.dp, end = 24.dp, bottom = 24.dp),
        )
    }
}

@Composable
private fun Tile(label: String, icon: Int, shape: androidx.graphics.shapes.RoundedPolygon, bg: Color, fg: Color, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(80.dp).clickable(onClick = onClick).padding(vertical = 4.dp)) {
        ShapeBadge(shape, bg, size = 64) { Icon(painterResource(icon), null, tint = fg, modifier = Modifier.size(28.dp)) }
        Text(label, style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(top = 8.dp), maxLines = 2)
    }
}
